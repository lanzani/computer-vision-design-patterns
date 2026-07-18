# -*- coding: utf-8 -*-
"""Supervisor — pipeline lifecycle, health/restart loop, dynamic streams."""

from __future__ import annotations

import multiprocessing as mp
import queue
import threading
import time
from dataclasses import dataclass, field, replace
from typing import Callable

from loguru import logger

from computer_vision_design_patterns.pipeline_v3.channel import (
    Channel,
    OverflowPolicy,
    make_channel,
)
from computer_vision_design_patterns.pipeline_v3.graph import (
    Edge,
    GraphValidationError,
    PipelineGraph,
)
from computer_vision_design_patterns.pipeline_v3.port import Port
from computer_vision_design_patterns.pipeline_v3.runner import StageRunner
from computer_vision_design_patterns.pipeline_v3.stage import ExecutorType, Stage, StageMetrics


@dataclass
class PipelineEvent:
    """Notification emitted by the supervisor (via the ``on_event`` callback)."""

    kind: str
    """One of: pipeline_started, pipeline_stopped, stream_added, stream_removed,
    stage_restarted, stage_failed, stage_stale."""

    stage_name: str | None = None
    stream_id: str | None = None
    ts: float = field(default_factory=time.time)


class Supervisor:
    """Orchestrates a PipelineGraph: start/stop, health, restarts, dynamic streams.

    Typical usage::

        sup = Supervisor(on_event=print)
        apartment = sup.add_stage(ApartmentAggregator("apartment-1"))
        sup.add_stream(
            "cam1",
            chain=[camera, pose],
            fanout={pose.poses_out: [fall, sink]},
            attach=[(pose.poses_out, apartment.port_for("cam1"))],
        )
        sup.start()
    """

    def __init__(
        self,
        graph: PipelineGraph | None = None,
        join_timeout: float = 5.0,
        health_interval_s: float = 0.5,
        heartbeat_timeout_s: float = 5.0,
        on_event: Callable[[PipelineEvent], None] | None = None,
        ctx: mp.context.BaseContext | None = None,
    ):
        self.graph = graph or PipelineGraph()
        self.join_timeout = join_timeout
        self.health_interval_s = health_interval_s
        self.heartbeat_timeout_s = heartbeat_timeout_s
        self.on_event = on_event
        self._ctx = ctx or mp.get_context("spawn")

        self._metrics_queue: mp.Queue = self._ctx.Queue(maxsize=4096)
        self._runners: dict[str, StageRunner] = {}
        self._edge_channels: dict[int, Channel] = {}  # id(edge) → channel
        self._stage_channels: dict[str, tuple[dict[str, Channel], dict[str, list[Channel]]]] = {}
        self._metrics: dict[str, StageMetrics] = {}
        self._metrics_received_at: dict[str, float] = {}
        self._restart_history: dict[str, list[float]] = {}
        self._failed_stages: set[str] = set()

        self._lock = threading.RLock()
        self._running = False
        self._health_thread: threading.Thread | None = None
        self._stop_health = threading.Event()

    # -- graph building --------------------------------------------------------

    def add_stage(self, stage: Stage, stream_id: str | None = None) -> Stage:
        with self._lock:
            return self.graph.add_stage(stage, stream_id=stream_id)

    def connect(
        self,
        source: Port | Stage,
        target: Port | Stage,
        policy: OverflowPolicy = OverflowPolicy.LATEST_ONLY,
        maxsize: int = 1,
        stream_id: str | None = None,
    ) -> Edge:
        with self._lock:
            return self.graph.connect(
                self._out_port(source),
                self._in_port(target),
                policy=policy,
                maxsize=maxsize,
                stream_id=stream_id,
            )

    def chain(
        self,
        *stages: Stage,
        policy: OverflowPolicy = OverflowPolicy.LATEST_ONLY,
        maxsize: int = 1,
        stream_id: str | None = None,
    ) -> list[Edge]:
        """Connect stages linearly (each single output → next single input)."""
        return [
            self.connect(a, b, policy=policy, maxsize=maxsize, stream_id=stream_id) for a, b in zip(stages, stages[1:])
        ]

    # -- lifecycle ----------------------------------------------------------------

    def start(self) -> None:
        with self._lock:
            if self._running:
                raise RuntimeError("Supervisor already running")
            self.graph.validate()
            self._build_runners(self.graph.stages, self.graph.edges)
            order = self.graph.topological_order()
            for stage in order:
                self._runners[stage.name].start()
            for stage in order:
                if not self._runners[stage.name].wait_ready(timeout=10.0):
                    logger.warning(f"Stage {stage.name!r} did not signal ready in time")
            self._running = True
            self._start_health_loop()
            logger.info(f"Pipeline started with {len(self._runners)} stages")
            self._emit_event("pipeline_started")

    def stop(self) -> None:
        with self._lock:
            if not self._running and not self._runners:
                return
            self._stop_health.set()
            health_thread = self._health_thread
            self._health_thread = None

        # Join the health thread outside the lock (it takes the lock itself).
        if health_thread is not None:
            health_thread.join(timeout=2.0)

        with self._lock:
            try:
                order = self.graph.topological_order()
            except GraphValidationError:
                order = list(self.graph.stages)

            # Stop sources first so the graph drains downstream.
            for stage in order:
                runner = self._runners.get(stage.name)
                if runner is not None:
                    runner.stop()

            # Close all channels so consumers get SENTINEL and stop waiting.
            for ch in self._edge_channels.values():
                try:
                    ch.close()
                except Exception:
                    logger.exception("Error closing channel")

            for stage in reversed(order):
                runner = self._runners.get(stage.name)
                if runner is not None:
                    runner.join(timeout=self.join_timeout)

            self._drain_metrics()
            self._runners.clear()
            self._edge_channels.clear()
            self._stage_channels.clear()
            self._restart_history.clear()
            self._failed_stages.clear()
            self._running = False
            logger.info("Pipeline stopped")
            self._emit_event("pipeline_stopped")

    def stats(self) -> dict[str, StageMetrics]:
        """Latest metrics snapshot per stage (copies — safe to keep)."""
        with self._lock:
            self._drain_metrics()
            return {name: replace(m) for name, m in self._metrics.items()}

    @property
    def is_running(self) -> bool:
        return self._running

    def __enter__(self) -> Supervisor:
        self.start()
        return self

    def __exit__(self, *args) -> None:
        self.stop()

    def __len__(self) -> int:
        return len(self.graph.stages)

    # -- dynamic streams -------------------------------------------------------------

    def add_stream(
        self,
        stream_id: str,
        chain: list[Stage] | None = None,
        fanout: dict[Port | Stage, list[Stage | Port]] | None = None,
        attach: list[tuple[Port | Stage, Port]] | None = None,
        *,
        policy: OverflowPolicy = OverflowPolicy.LATEST_ONLY,
        maxsize: int = 1,
    ) -> None:
        """Add a stream sub-graph — before start or while running (same code path).

        - ``chain``: new stages connected linearly (source → … ).
        - ``fanout``: {source port/stage → [new target stages/ports]}.
        - ``attach``: edges from new stages to *already existing* stages
          (e.g. pose → apartment aggregator). A running attach target must be
          a THREAD stage; hot-attaching to a running PROCESS stage is impossible
          (its channels are fixed at spawn) and raises immediately.
        """
        with self._lock:
            if self.graph.has_stream(stream_id):
                raise ValueError(f"Stream {stream_id!r} already exists")

            new_stages: list[Stage] = []
            new_ids: set[int] = set()
            graph_ids = {id(s) for s in self.graph.stages}

            def register(stage: Stage) -> None:
                if id(stage) in graph_ids:
                    raise GraphValidationError(
                        f"Stage {stage.name!r} is already in the graph; "
                        f"use attach=[...] to connect new stages to existing ones"
                    )
                if id(stage) not in new_ids:
                    new_ids.add(id(stage))
                    new_stages.append(stage)

            pairs: list[tuple[Port, Port]] = []

            chain = chain or []
            for stage in chain:
                register(stage)
            for a, b in zip(chain, chain[1:]):
                pairs.append((self._out_port(a), self._in_port(b)))

            for src, targets in (fanout or {}).items():
                src_port = self._out_port(src)
                register(src_port.stage)
                for t in targets:
                    tgt_port = self._in_port(t)
                    register(tgt_port.stage)
                    pairs.append((src_port, tgt_port))

            for stage in new_stages:
                self.graph.add_stage(stage, stream_id=stream_id)

            new_edges = [
                self.graph.connect(s, t, policy=policy, maxsize=maxsize, stream_id=stream_id) for s, t in pairs
            ]

            attach_edges: list[Edge] = []
            for s, t in attach or []:
                s_port = self._out_port(s)
                t_port = self._in_port(t)
                for port in (s_port, t_port):
                    if id(port.stage) not in graph_ids and id(port.stage) not in new_ids:
                        raise GraphValidationError(
                            f"attach stage {port.stage.name!r} is neither in the graph "
                            f"nor part of this stream's chain/fanout"
                        )
                attach_edges.append(
                    self.graph.connect(s_port, t_port, policy=policy, maxsize=maxsize, stream_id=stream_id)
                )

            if not self._running:
                self._emit_event("stream_added", stream_id=stream_id)
                return

            # -- runtime wiring --
            for edge in attach_edges:
                for stage_side in (edge.source.stage, edge.target.stage):
                    runner = self._runners.get(stage_side.name)
                    if runner is not None and stage_side.executor == ExecutorType.PROCESS:
                        raise RuntimeError(
                            f"Cannot hot-attach to running PROCESS stage {stage_side.name!r}; "
                            f"dynamic fan-in/fan-out stages must use ExecutorType.THREAD"
                        )

            self._build_runners(new_stages, new_edges + attach_edges, existing_ok=True)

            # Wire attach edges into the already-running side(s); new stages got
            # their channels from _build_runners.
            for edge in attach_edges:
                ch = self._edge_channels[id(edge)]
                if id(edge.target.stage) not in new_ids:
                    self._runners[edge.target.stage.name].add_input_channel(edge.target.name, ch)
                if id(edge.source.stage) not in new_ids:
                    self._runners[edge.source.stage.name].add_output_channel(edge.source.name, ch)

            for stage in new_stages:
                runner = self._runners[stage.name]
                runner.start()
                runner.wait_ready(timeout=10.0)

            logger.info(f"Added stream {stream_id!r} with {len(new_stages)} stages")
            self._emit_event("stream_added", stream_id=stream_id)

    def remove_stream(self, stream_id: str, join_timeout: float | None = None) -> None:
        """Stop and detach a stream sub-graph.

        Stream channels are closed so surviving fan-in stages observe SENTINEL
        on the affected port and clean up via ``on_port_closed``.
        """
        with self._lock:
            if not self.graph.has_stream(stream_id):
                raise ValueError(f"Unknown stream {stream_id!r}")

            timeout = join_timeout if join_timeout is not None else self.join_timeout
            stages = self.graph.stages_for_stream(stream_id)
            stage_names = {s.name for s in stages}
            edges = self.graph.edges_for_stream(stream_id)

            for stage in stages:
                runner = self._runners.get(stage.name)
                if runner is not None:
                    runner.stop()

            for edge in edges:
                ch = self._edge_channels.pop(id(edge), None)
                if ch is not None:
                    try:
                        ch.close()
                    except Exception:
                        logger.exception("Error closing stream channel")

            for stage in reversed(stages):
                runner = self._runners.pop(stage.name, None)
                if runner is not None:
                    runner.join(timeout=timeout)
                self._metrics.pop(stage.name, None)
                self._metrics_received_at.pop(stage.name, None)
                self._stage_channels.pop(stage.name, None)
                self._restart_history.pop(stage.name, None)
                self._failed_stages.discard(stage.name)

            # Prune attach-edge target ports on surviving stages (the worker
            # also does this via SENTINEL → on_port_closed; both are idempotent).
            for edge in edges:
                if edge.target.stage.name not in stage_names:
                    edge.target.stage._input_ports.pop(edge.target.name, None)

            self.graph.remove_stream(stream_id)
            logger.info(f"Removed stream {stream_id!r}")
            self._emit_event("stream_removed", stream_id=stream_id)

    # -- internals ---------------------------------------------------------------------

    @classmethod
    def _out_port(cls, x: Port | Stage) -> Port:
        return cls._single_port(x, "out")

    @classmethod
    def _in_port(cls, x: Port | Stage) -> Port:
        return cls._single_port(x, "in")

    @staticmethod
    def _single_port(x: Port | Stage, direction: str) -> Port:
        """Resolve a Port, or a Stage's only port in the given direction."""
        kind = "output" if direction == "out" else "input"
        if isinstance(x, Port):
            if x.direction != direction:
                raise GraphValidationError(f"{x} is not an {kind} port")
            return x
        ports = x.outputs if direction == "out" else x.inputs
        if len(ports) != 1:
            raise GraphValidationError(f"Stage {x.name!r} has {len(ports)} {kind} ports; specify one explicitly")
        return next(iter(ports.values()))

    def _build_runners(
        self,
        stages: list[Stage],
        edges: list[Edge],
        existing_ok: bool = False,
    ) -> None:
        for edge in edges:
            cross_process = (
                edge.source.stage.executor == ExecutorType.PROCESS or edge.target.stage.executor == ExecutorType.PROCESS
            )
            self._edge_channels[id(edge)] = make_channel(
                cross_process=cross_process,
                maxsize=edge.maxsize,
                policy=edge.policy,
                ctx=self._ctx,
            )

        input_map: dict[str, dict[str, Channel]] = {s.name: {} for s in stages}
        output_map: dict[str, dict[str, list[Channel]]] = {s.name: {} for s in stages}

        for edge in self.graph.edges:
            ch = self._edge_channels.get(id(edge))
            if ch is None:
                continue
            if edge.source.stage.name in output_map:
                output_map[edge.source.stage.name].setdefault(edge.source.name, []).append(ch)
            if edge.target.stage.name in input_map:
                input_map[edge.target.stage.name][edge.target.name] = ch

        for stage in stages:
            if stage.name in self._runners:
                if existing_ok:
                    continue
                raise RuntimeError(f"Runner already exists for {stage.name!r}")
            self._stage_channels[stage.name] = (input_map[stage.name], output_map[stage.name])
            self._runners[stage.name] = self._make_runner(stage)
            self._metrics.setdefault(stage.name, StageMetrics(stage_name=stage.name))

    def _make_runner(self, stage: Stage) -> StageRunner:
        in_map, out_map = self._stage_channels[stage.name]
        return StageRunner(
            stage=stage,
            input_channels=in_map,
            output_channels=out_map,
            metrics_queue=self._metrics_queue,
            join_timeout=self.join_timeout,
            ctx=self._ctx,
        )

    # -- health / restarts -----------------------------------------------------------

    def _drain_metrics(self) -> None:
        now = time.time()
        while True:
            try:
                m = self._metrics_queue.get_nowait()
            except queue.Empty:
                break
            except (ValueError, OSError):
                break
            self._metrics[m.stage_name] = m
            self._metrics_received_at[m.stage_name] = now

    def _start_health_loop(self) -> None:
        self._stop_health.clear()

        def _loop() -> None:
            while not self._stop_health.wait(timeout=self.health_interval_s):
                with self._lock:
                    if not self._running:
                        continue
                    self._drain_metrics()
                    now = time.time()
                    for name, runner in list(self._runners.items()):
                        if runner.is_alive():
                            received = self._metrics_received_at.get(name)
                            if received is not None and now - received > self.heartbeat_timeout_s:
                                m = self._metrics.get(name)
                                if m is not None and m.healthy:
                                    m.healthy = False
                                    logger.warning(f"Stage {name!r} heartbeat is stale")
                                    self._emit_event("stage_stale", stage_name=name)
                            continue

                        if runner.stop_requested or name in self._failed_stages:
                            continue  # intentional stop or already given up

                        self._handle_dead_stage(name)

        self._health_thread = threading.Thread(target=_loop, name="pipeline-health", daemon=True)
        self._health_thread.start()

    def _handle_dead_stage(self, name: str) -> None:
        """Called under lock when a worker died without being asked to stop."""
        stage = self.graph.get_stage(name)
        if stage is None:
            return

        now = time.time()
        policy = stage.error_policy
        history = self._restart_history.setdefault(name, [])
        history[:] = [t for t in history if now - t < policy.restart_window_s]

        if len(history) >= policy.max_restarts:
            self._failed_stages.add(name)
            m = self._metrics.get(name)
            if m is not None:
                m.healthy = False
            logger.error(
                f"Stage {name!r} exceeded {policy.max_restarts} restarts in {policy.restart_window_s}s — marking failed"
            )
            self._emit_event("stage_failed", stage_name=name)
            return

        history.append(now)
        logger.warning(f"Stage {name!r} died unexpectedly — restarting ({len(history)}/{policy.max_restarts})")
        runner = self._make_runner(stage)
        self._runners[name] = runner
        runner.start()
        runner.wait_ready(timeout=5.0)
        self._emit_event("stage_restarted", stage_name=name)

    def _emit_event(self, kind: str, **kwargs) -> None:
        if self.on_event is None:
            return
        try:
            self.on_event(PipelineEvent(kind=kind, **kwargs))
        except Exception:
            logger.exception("on_event callback failed")
