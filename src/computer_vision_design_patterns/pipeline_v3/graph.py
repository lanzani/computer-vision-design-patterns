# -*- coding: utf-8 -*-
"""Declarative pipeline graph with validation."""

from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass, field

from computer_vision_design_patterns.pipeline_v3.channel import OverflowPolicy
from computer_vision_design_patterns.pipeline_v3.port import Port
from computer_vision_design_patterns.pipeline_v3.stage import Stage


class GraphValidationError(Exception):
    """Raised when the pipeline graph is invalid."""


@dataclass(slots=True)
class Edge:
    """A directed connection from an output port to an input port."""

    source: Port
    target: Port
    policy: OverflowPolicy = OverflowPolicy.LATEST_ONLY
    maxsize: int = 1
    stream_id: str | None = None
    """Optional tag used for dynamic add/remove of stream sub-graphs."""


@dataclass
class PipelineGraph:
    """Declarative wiring of stages via typed ports."""

    stages: list[Stage] = field(default_factory=list)
    edges: list[Edge] = field(default_factory=list)
    _stream_tags: dict[str, set[str]] = field(default_factory=lambda: defaultdict(set))
    """stream_id → set of stage names belonging to that stream."""

    def add_stage(self, stage: Stage, stream_id: str | None = None) -> Stage:
        if any(s.name == stage.name for s in self.stages):
            raise GraphValidationError(f"Duplicate stage name: {stage.name!r}")
        self.stages.append(stage)
        if stream_id is not None:
            self._stream_tags[stream_id].add(stage.name)
        return stage

    def get_stage(self, name: str) -> Stage | None:
        for stage in self.stages:
            if stage.name == name:
                return stage
        return None

    def has_stream(self, stream_id: str) -> bool:
        return stream_id in self._stream_tags

    def connect(
        self,
        source: Port,
        target: Port,
        policy: OverflowPolicy = OverflowPolicy.LATEST_ONLY,
        maxsize: int = 1,
        stream_id: str | None = None,
    ) -> Edge:
        if source.direction != "out":
            raise GraphValidationError(f"Source port must be an output: {source}")
        if target.direction != "in":
            raise GraphValidationError(f"Target port must be an input: {target}")

        # The producer's packets must be acceptable by the consumer: the
        # source type must be the target type or a subclass of it.
        if not issubclass(source.packet_type, target.packet_type):
            raise GraphValidationError(
                f"Port type mismatch: {source} emits {source.packet_type.__name__}, "
                f"but {target} accepts {target.packet_type.__name__}"
            )

        # Exactly one edge per input port — silent fan-in overwrites were a
        # major bug class in the previous design.
        if any(e.target == target for e in self.edges):
            raise GraphValidationError(
                f"Input port {target} already has an incoming edge; "
                f"declare one input port per producer (see AggregatorStage.port_for)"
            )

        edge = Edge(
            source=source,
            target=target,
            policy=policy,
            maxsize=maxsize,
            stream_id=stream_id,
        )
        self.edges.append(edge)
        return edge

    def stages_for_stream(self, stream_id: str) -> list[Stage]:
        names = self._stream_tags.get(stream_id, set())
        return [s for s in self.stages if s.name in names]

    def edges_for_stream(self, stream_id: str) -> list[Edge]:
        return [e for e in self.edges if e.stream_id == stream_id]

    def remove_stream(self, stream_id: str) -> tuple[list[Stage], list[Edge]]:
        """Remove stages/edges tagged with ``stream_id``. Returns what was removed."""
        stage_names = self._stream_tags.pop(stream_id, set())
        removed_stages = [s for s in self.stages if s.name in stage_names]
        self.stages = [s for s in self.stages if s.name not in stage_names]
        removed_edges = [
            e
            for e in self.edges
            if e.stream_id == stream_id or e.source.stage.name in stage_names or e.target.stage.name in stage_names
        ]
        removed_ids = {id(e) for e in removed_edges}
        self.edges = [e for e in self.edges if id(e) not in removed_ids]
        return removed_stages, removed_edges

    def validate(self) -> None:
        """Validate the graph before start. Raises GraphValidationError on failure.

        Unconnected *output* ports are allowed (their packets are dropped);
        unconnected *input* ports are errors, since the stage would wait forever.
        """
        if not self.stages:
            raise GraphValidationError("Graph has no stages")

        stage_ids = {id(s) for s in self.stages}
        for edge in self.edges:
            if id(edge.source.stage) not in stage_ids:
                raise GraphValidationError(f"Edge source stage {edge.source.stage.name!r} is not in the graph")
            if id(edge.target.stage) not in stage_ids:
                raise GraphValidationError(f"Edge target stage {edge.target.stage.name!r} is not in the graph")

        connected_in = {(id(e.target.stage), e.target.name) for e in self.edges}
        for stage in self.stages:
            for name in stage.inputs:
                if (id(stage), name) not in connected_in:
                    raise GraphValidationError(f"Dangling input port: {stage.name}.{name}")

        self.topological_order()  # raises on cycle

    def topological_order(self) -> list[Stage]:
        """Return stages in topological order (sources first). Raises on cycle."""
        indegree: dict[int, int] = {id(s): 0 for s in self.stages}
        children: dict[int, list[Stage]] = defaultdict(list)
        for edge in self.edges:
            children[id(edge.source.stage)].append(edge.target.stage)
            indegree[id(edge.target.stage)] += 1

        ready: deque[Stage] = deque(s for s in self.stages if indegree[id(s)] == 0)
        order: list[Stage] = []
        while ready:
            stage = ready.popleft()
            order.append(stage)
            for child in children[id(stage)]:
                indegree[id(child)] -= 1
                if indegree[id(child)] == 0:
                    ready.append(child)

        if len(order) != len(self.stages):
            raise GraphValidationError("Graph contains a cycle (topo sort incomplete)")
        return order
