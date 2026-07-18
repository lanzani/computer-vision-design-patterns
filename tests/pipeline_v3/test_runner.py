# -*- coding: utf-8 -*-
"""Tests for StageRunner / worker loop behavior (THREAD executor)."""

from __future__ import annotations

import time

from computer_vision_design_patterns.pipeline_v3.channel import OverflowPolicy, ThreadChannel
from computer_vision_design_patterns.pipeline_v3.packet import FramePacket, Packet
from computer_vision_design_patterns.pipeline_v3.runner import StageRunner
from computer_vision_design_patterns.pipeline_v3.stage import (
    ErrorPolicy,
    SinkStage,
    SourceStage,
    Stage,
    StopStage,
)


class TickSource(SourceStage):
    """Emits sequential packets; optionally fails ``fail_first`` reads."""

    def __init__(self, name="tick-src", target_fps=None, fail_always=False):
        super().__init__(name=name, target_fps=target_fps, read_backoff_s=0.01)
        self.fail_always = fail_always
        self.out = self.add_output("out", FramePacket)

    def read(self) -> Packet | None:
        if self.fail_always:
            return None
        return FramePacket(stream_id="s", seq=self.next_seq())


class CollectSink(SinkStage):
    def __init__(self, name="collect", stop_after: int | None = None):
        super().__init__(name=name)
        self.inp = self.add_input("in", FramePacket)
        self.received: list[int] = []
        self.stop_after = stop_after

    def consume(self, port_name: str, packet: Packet) -> None:
        self.received.append(packet.seq)
        if self.stop_after is not None and len(self.received) >= self.stop_after:
            raise StopStage("done")


class AlwaysFails(Stage):
    def __init__(self):
        super().__init__(
            name="broken",
            error_policy=ErrorPolicy(max_consecutive_failures=2, initial_backoff_s=0.01),
        )
        self.inp = self.add_input("in", FramePacket)

    def process(self, inputs):
        raise RuntimeError("boom")


class PortTracker(Stage):
    """Two-input passthrough that records closed ports."""

    def __init__(self):
        super().__init__(name="tracker")
        self.a = self.add_input("a", FramePacket)
        self.b = self.add_input("b", FramePacket)
        self.closed: list[str] = []

    def on_port_closed(self, port_name: str) -> None:
        self.closed.append(port_name)

    def process(self, inputs):
        return None


def _wait_until(predicate, timeout=3.0, step=0.02) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if predicate():
            return True
        time.sleep(step)
    return False


def test_source_to_sink_roundtrip():
    src = TickSource()
    sink = CollectSink()
    ch = ThreadChannel(policy=OverflowPolicy.BLOCK, maxsize=8)

    r_src = StageRunner(src, output_channels={"out": [ch]})
    r_sink = StageRunner(sink, input_channels={"in": ch})
    r_src.start()
    r_sink.start()
    try:
        assert _wait_until(lambda: len(sink.received) >= 5)
    finally:
        r_src.stop()
        r_sink.stop()
        r_src.join()
        r_sink.join()
    assert not r_src.is_alive()
    assert not r_sink.is_alive()


def test_stop_stage_is_graceful_and_marks_stop_requested():
    src = TickSource()
    sink = CollectSink(stop_after=3)
    ch = ThreadChannel(policy=OverflowPolicy.BLOCK, maxsize=8)

    r_src = StageRunner(src, output_channels={"out": [ch]})
    r_sink = StageRunner(sink, input_channels={"in": ch})
    r_src.start()
    r_sink.start()
    try:
        assert _wait_until(lambda: not r_sink.is_alive())
        # StopStage sets the stop event → supervisor treats it as intentional.
        assert r_sink.stop_requested is True
        assert len(sink.received) == 3
    finally:
        r_src.stop()
        r_src.join()
        r_sink.join()


def test_error_exhaustion_exits_without_stop_requested():
    stage = AlwaysFails()
    ch = ThreadChannel(policy=OverflowPolicy.BLOCK, maxsize=8)
    ch.put(FramePacket(stream_id="s", seq=1))
    ch.put(FramePacket(stream_id="s", seq=2))
    ch.put(FramePacket(stream_id="s", seq=3))

    runner = StageRunner(stage, input_channels={"in": ch})
    runner.start()
    assert _wait_until(lambda: not runner.is_alive())
    # The worker died from errors — stop was NOT requested → restartable.
    assert runner.stop_requested is False
    runner.join()


def test_sentinel_closes_port_but_stage_keeps_running():
    stage = PortTracker()
    ch_a = ThreadChannel(policy=OverflowPolicy.BLOCK, maxsize=4)
    ch_b = ThreadChannel(policy=OverflowPolicy.BLOCK, maxsize=4)

    runner = StageRunner(stage, input_channels={"a": ch_a, "b": ch_b})
    runner.start()
    try:
        ch_a.close()
        assert _wait_until(lambda: "a" in stage.closed)
        assert runner.is_alive()  # fan-in stages survive losing one port
        assert "a" not in runner.input_channels
        assert "b" in runner.input_channels

        ch_b.close()
        assert _wait_until(lambda: "b" in stage.closed)
        assert runner.is_alive()  # stop is the supervisor's decision
    finally:
        runner.stop()
        runner.join()


def test_target_fps_paces_source():
    src = TickSource(target_fps=20.0)
    sink = CollectSink()
    ch = ThreadChannel(policy=OverflowPolicy.BLOCK, maxsize=64)

    r_src = StageRunner(src, output_channels={"out": [ch]})
    r_sink = StageRunner(sink, input_channels={"in": ch})
    r_src.start()
    r_sink.start()
    time.sleep(1.0)
    r_src.stop()
    r_sink.stop()
    r_src.join()
    r_sink.join()
    # 20 fps over ~1s: allow generous margins for CI timers.
    assert 5 <= len(sink.received) <= 45


def test_failing_source_backs_off_instead_of_spinning():
    src = TickSource(fail_always=True)
    runner = StageRunner(src, output_channels={"out": [ThreadChannel()]})
    runner.start()
    time.sleep(0.3)
    try:
        assert runner.is_alive()  # still healthy, just idle-backing-off
    finally:
        runner.stop()
        runner.join()
