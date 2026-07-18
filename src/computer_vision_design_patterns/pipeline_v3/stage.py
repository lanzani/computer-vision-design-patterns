# -*- coding: utf-8 -*-
"""Stage ABC and specializations (Source, Sink, Aggregator)."""

from __future__ import annotations

import dataclasses
import time
from abc import ABC, abstractmethod
from collections import defaultdict, deque
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Type

from computer_vision_design_patterns.pipeline_v3.packet import Packet
from computer_vision_design_patterns.pipeline_v3.port import Port


class ExecutorType(Enum):
    THREAD = auto()
    PROCESS = auto()


class StopStage(Exception):
    """Raised from ``process()`` to request a graceful stop of this stage.

    Unlike an error, a StopStage exit sets the runner's stop event, so the
    supervisor treats it as intentional and will not restart the stage.
    """


@dataclass
class ErrorPolicy:
    """How the runner and supervisor react to failures of this stage."""

    max_consecutive_failures: int = 5
    """Consecutive ``process()`` failures before the worker exits."""

    initial_backoff_s: float = 0.05
    max_backoff_s: float = 2.0
    backoff_factor: float = 2.0

    max_restarts: int = 3
    """How many times the supervisor may restart a dead worker..."""

    restart_window_s: float = 60.0
    """...within this rolling window, before marking the stage failed."""


@dataclass
class StageMetrics:
    """Runtime metrics snapshot emitted by a StageRunner over the control bus."""

    stage_name: str = ""
    pid: int = 0
    processed: int = 0
    errors: int = 0
    drops: int = 0
    last_latency_ms: float = 0.0
    fps: float = 0.0
    healthy: bool = True
    last_heartbeat: float = field(default_factory=time.time)


class Stage(ABC):
    """Pure processing unit. Never touches queues, events, or workers.

    Subclasses declare typed ports and implement ``process``. The StageRunner
    owns the worker loop, error policy, and metrics.
    """

    def __init__(
        self,
        name: str,
        executor: ExecutorType = ExecutorType.THREAD,
        error_policy: ErrorPolicy | None = None,
    ):
        self.name = name
        self.executor = executor
        self.error_policy = error_policy or ErrorPolicy()
        self._input_ports: dict[str, Port] = {}
        self._output_ports: dict[str, Port] = {}

    # -- port declaration helpers -------------------------------------------

    def add_input(self, name: str, packet_type: Type[Packet]) -> Port:
        port = Port(stage=self, name=name, packet_type=packet_type, direction="in")
        self._input_ports[name] = port
        return port

    def add_output(self, name: str, packet_type: Type[Packet]) -> Port:
        port = Port(stage=self, name=name, packet_type=packet_type, direction="out")
        self._output_ports[name] = port
        return port

    @property
    def inputs(self) -> dict[str, Port]:
        return self._input_ports

    @property
    def outputs(self) -> dict[str, Port]:
        return self._output_ports

    # -- lifecycle ----------------------------------------------------------

    def setup(self) -> None:
        """Called once in the worker before the processing loop."""

    def teardown(self) -> None:
        """Called once after the processing loop exits."""

    def on_port_closed(self, port_name: str) -> None:
        """Called by the runner when an input edge closes (e.g. stream removed).

        Default is a no-op; fan-in stages override to free per-port state.
        """

    @abstractmethod
    def process(self, inputs: dict[str, Packet]) -> dict[str, Packet | None] | None:
        """Process one tick.

        ``inputs`` maps input port name → packet, containing only the ports
        that received data this tick (sources get an empty dict). Return a
        dict mapping output port name → packet, or None to emit nothing.

        Raise ``StopStage`` to request a graceful, non-restartable stop.
        """


class SourceStage(Stage):
    """Stage with no inputs that produces packets by reading an external source.

    Pacing lives in the runner: when ``read()`` returns None the runner backs
    off exponentially (stop-aware, so shutdown is immediate); ``target_fps``
    caps the emit rate. Sources never busy-spin and never block shutdown.
    """

    def __init__(
        self,
        name: str,
        executor: ExecutorType = ExecutorType.THREAD,
        error_policy: ErrorPolicy | None = None,
        target_fps: float | None = None,
        read_backoff_s: float = 0.05,
        max_read_backoff_s: float = 2.0,
    ):
        super().__init__(name=name, executor=executor, error_policy=error_policy)
        self.target_fps = target_fps
        self.read_backoff_s = read_backoff_s
        self.max_read_backoff_s = max_read_backoff_s
        self._seq = 0

    def next_seq(self) -> int:
        self._seq += 1
        return self._seq

    def process(self, inputs: dict[str, Packet]) -> dict[str, Packet | None] | None:
        packet = self.read()
        if packet is None or not self._output_ports:
            return None
        out_name = next(iter(self._output_ports))
        return {out_name: packet}

    @abstractmethod
    def read(self) -> Packet | None:
        """Read one packet from the external source, or None on failure / EOF.

        Must not sleep — the runner handles backoff and pacing.
        """


class SinkStage(Stage):
    """Stage with no outputs that consumes packets (display, log, store, …)."""

    def process(self, inputs: dict[str, Packet]) -> dict[str, Packet | None] | None:
        for port_name, packet in inputs.items():
            self.consume(port_name, packet)
        return None

    @abstractmethod
    def consume(self, port_name: str, packet: Packet) -> None:
        """Handle one inbound packet. Raise StopStage to stop gracefully."""


class AggregatorStage(Stage):
    """Fan-in stage that aggregates packets from multiple input ports.

    Ports are created per stream via ``port_for(stream_id)``, so the graph can
    grow at runtime. Frames are stripped on ingest by default so the buffers
    hold lightweight results (keypoints, events) instead of megabytes of
    pixels. Aggregation is deduplicated: the same combination of packets is
    never emitted twice.
    """

    def __init__(
        self,
        name: str,
        executor: ExecutorType = ExecutorType.THREAD,
        error_policy: ErrorPolicy | None = None,
        window_s: float = 0.5,
        max_buffer: int = 32,
        strip_frames: bool = True,
    ):
        super().__init__(name=name, executor=executor, error_policy=error_policy)
        self.window_s = window_s
        self.max_buffer = max_buffer
        self.strip_frames = strip_frames
        self._buffers: dict[str, deque[Packet]] = defaultdict(deque)
        self._last_signature: tuple | None = None

    def port_for(self, stream_id: str, packet_type: Type[Packet] = Packet) -> Port:
        """Get or create the input port for a stream (named ``in-<stream_id>``)."""
        port_name = f"in-{stream_id}"
        existing = self._input_ports.get(port_name)
        if existing is not None:
            return existing
        return self.add_input(port_name, packet_type)

    def on_port_closed(self, port_name: str) -> None:
        self._buffers.pop(port_name, None)
        self._input_ports.pop(port_name, None)
        self._last_signature = None

    def process(self, inputs: dict[str, Packet]) -> dict[str, Packet | None] | None:
        for port_name, packet in inputs.items():
            if self.strip_frames:
                packet = _strip_frames(packet)
            buf = self._buffers[port_name]
            buf.append(packet)
            while len(buf) > self.max_buffer:
                buf.popleft()

        aligned = self.align_window()
        if not aligned:
            return None

        signature = tuple(sorted((port, pkt.seq) for port, pkt in aligned.items()))
        if signature == self._last_signature:
            return None
        self._last_signature = signature

        return self.aggregate(aligned)

    def align_window(self) -> dict[str, Packet] | None:
        """Return the newest packet per port whose timestamps fall within ``window_s``."""
        latest: dict[str, Packet] = {}
        for port_name, buf in self._buffers.items():
            if buf:
                latest[port_name] = buf[-1]

        if not latest:
            return None

        timestamps = [p.ts_capture for p in latest.values()]
        if max(timestamps) - min(timestamps) > self.window_s:
            return None

        return latest

    @abstractmethod
    def aggregate(self, aligned: dict[str, Packet]) -> dict[str, Packet | None] | None:
        """Combine aligned multi-stream packets into output packet(s)."""


def _strip_frames(packet: Packet) -> Packet:
    """Drop heavy frame payloads from a packet, if it has any."""
    updates = {field: None for field in ("frame", "frame_ref") if getattr(packet, field, None) is not None}
    return dataclasses.replace(packet, **updates) if updates else packet
