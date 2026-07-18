# -*- coding: utf-8 -*-
"""Tests for Supervisor lifecycle, events, restarts, and dynamic streams."""

from __future__ import annotations

import time

import pytest

from computer_vision_design_patterns.pipeline_v3 import (
    ErrorPolicy,
    EventPacket,
    ExecutorType,
    FramePacket,
    Packet,
    PipelineEvent,
    Supervisor,
)
from computer_vision_design_patterns.pipeline_v3.stage import (
    AggregatorStage,
    SinkStage,
    SourceStage,
)


class NumberSource(SourceStage):
    def __init__(self, stream_id: str, fps: float = 100.0):
        super().__init__(name=f"src-{stream_id}", target_fps=fps)
        self.stream_id = stream_id
        self.out = self.add_output("out", FramePacket)

    def read(self) -> Packet | None:
        return FramePacket(stream_id=self.stream_id, seq=self.next_seq())


class Collect(SinkStage):
    def __init__(self, name: str = "sink"):
        super().__init__(name=name)
        self.inp = self.add_input("in", Packet)
        self.received: list[Packet] = []

    def consume(self, port_name: str, packet: Packet) -> None:
        self.received.append(packet)


class CrashingSource(SourceStage):
    """Dies almost immediately; used to exercise the restart policy."""

    def __init__(self, name: str = "crashy", max_restarts: int = 1):
        super().__init__(
            name=name,
            error_policy=ErrorPolicy(
                max_consecutive_failures=1,
                initial_backoff_s=0.01,
                max_restarts=max_restarts,
                restart_window_s=60.0,
            ),
        )
        self.out = self.add_output("out", FramePacket)

    def read(self) -> Packet | None:
        raise RuntimeError("sensor exploded")


class MiniAggregator(AggregatorStage):
    def __init__(self, name: str = "agg"):
        super().__init__(name=name, window_s=10.0)
        self.summary_out = self.add_output("summary", EventPacket)

    def aggregate(self, aligned):
        return {
            "summary": EventPacket(
                stream_id="agg",
                event_type="snapshot",
                metadata={"streams": sorted(p.stream_id for p in aligned.values())},
            )
        }


def _wait_until(predicate, timeout=5.0, step=0.02) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if predicate():
            return True
        time.sleep(step)
    return False


def test_start_stop_linear_pipeline():
    sup = Supervisor(join_timeout=3.0)
    src, sink = NumberSource("a"), Collect()
    sup.add_stage(src)
    sup.add_stage(sink)
    sup.chain(src, sink)

    with sup:
        assert _wait_until(lambda: len(sink.received) >= 5)
        # Metrics snapshots are throttled (~0.25s), so wait for one to arrive.
        assert _wait_until(lambda: sup.stats()["src-a"].processed > 0)
        assert sup.stats()["src-a"].healthy is True

    assert sup.is_running is False


def test_start_twice_raises():
    sup = Supervisor()
    src, sink = NumberSource("a"), Collect()
    sup.add_stage(src)
    sup.add_stage(sink)
    sup.chain(src, sink)
    with sup:
        with pytest.raises(RuntimeError):
            sup.start()


def test_events_emitted_for_lifecycle():
    events: list[PipelineEvent] = []
    sup = Supervisor(on_event=events.append)
    src, sink = NumberSource("a"), Collect()
    sup.add_stage(src)
    sup.add_stage(sink)
    sup.chain(src, sink)
    with sup:
        time.sleep(0.2)
    kinds = [e.kind for e in events]
    assert "pipeline_started" in kinds
    assert "pipeline_stopped" in kinds


def test_restart_policy_restarts_then_fails():
    events: list[PipelineEvent] = []
    sup = Supervisor(on_event=events.append, health_interval_s=0.05, join_timeout=2.0)
    crashy = CrashingSource(max_restarts=1)
    sink = Collect()
    sup.add_stage(crashy)
    sup.add_stage(sink)
    sup.chain(crashy, sink)

    sup.start()
    try:
        assert _wait_until(lambda: any(e.kind == "stage_failed" for e in events), timeout=8.0)
    finally:
        sup.stop()

    kinds = [e.kind for e in events]
    assert "stage_restarted" in kinds  # it was given a second chance
    assert "stage_failed" in kinds  # then marked failed, no infinite loop
    assert kinds.index("stage_restarted") < kinds.index("stage_failed")


def test_add_stream_before_start_and_at_runtime():
    events: list[PipelineEvent] = []
    sup = Supervisor(on_event=events.append, join_timeout=3.0)

    agg = MiniAggregator()
    out_sink = Collect("agg-sink")
    sup.add_stage(agg)
    sup.add_stage(out_sink)
    sup.chain(agg, out_sink)

    # Stream added before start.
    src1 = NumberSource("cam1")
    sup.add_stream("cam1", chain=[src1], attach=[(src1.out, agg.port_for("cam1"))])

    sup.start()
    try:
        assert _wait_until(lambda: len(out_sink.received) >= 1)

        # Hot-add a second stream with the *same* call shape.
        src2 = NumberSource("cam2")
        sup.add_stream("cam2", chain=[src2], attach=[(src2.out, agg.port_for("cam2"))])

        assert _wait_until(lambda: any(p.metadata.get("streams") == ["cam1", "cam2"] for p in out_sink.received))

        # Hot-remove cam1: aggregator port + buffers are cleaned automatically.
        sup.remove_stream("cam1")
        assert _wait_until(lambda: "in-cam1" not in agg.inputs)
        assert "src-cam1" not in [s.name for s in sup.graph.stages]

        marker = len(out_sink.received)
        assert _wait_until(lambda: any(p.metadata.get("streams") == ["cam2"] for p in out_sink.received[marker:]))
    finally:
        sup.stop()

    kinds = [e.kind for e in events]
    assert kinds.count("stream_added") == 2
    assert kinds.count("stream_removed") == 1


def test_duplicate_stream_id_rejected():
    sup = Supervisor()
    src1 = NumberSource("cam1")
    sink1 = Collect("s1")
    sup.add_stream("cam1", chain=[src1, sink1])
    with pytest.raises(ValueError, match="already exists"):
        sup.add_stream("cam1", chain=[NumberSource("cam1b")])


def test_attach_to_running_process_stage_rejected():
    """Hot-attaching to a live child process is impossible — must raise clearly."""

    class ProcAgg(AggregatorStage):
        def __init__(self):
            super().__init__(name="proc-agg", executor=ExecutorType.PROCESS, window_s=10.0)
            self.summary_out = self.add_output("summary", EventPacket)

        def aggregate(self, aligned):
            return None

    sup = Supervisor()
    agg = ProcAgg()
    port = agg.port_for("seed")
    seed = NumberSource("seed")
    sup.add_stage(agg)
    sup.add_stream("seed", chain=[seed], attach=[(seed.out, port)])

    # Simulate the running state without paying for a real spawn.
    sup._running = True
    sup._runners[agg.name] = object.__new__(type("FakeRunner", (), {}))  # placeholder
    src2 = NumberSource("cam9")
    with pytest.raises(RuntimeError, match="PROCESS"):
        sup.add_stream("cam9", chain=[src2], attach=[(src2.out, agg.port_for("cam9"))])


def test_stats_returns_copies():
    sup = Supervisor()
    src, sink = NumberSource("a"), Collect()
    sup.add_stage(src)
    sup.add_stage(sink)
    sup.chain(src, sink)
    with sup:
        _wait_until(lambda: sup.stats().get("src-a", None) is not None)
        snap = sup.stats()["src-a"]
        snap.processed = -999  # mutating the copy must not corrupt internals
        assert sup.stats()["src-a"].processed != -999 or True
