# -*- coding: utf-8 -*-
"""Unit tests for Stage specializations — pure logic, no runners needed."""

from __future__ import annotations

import numpy as np

from computer_vision_design_patterns.pipeline_v3.packet import EventPacket, Packet, PosePacket
from computer_vision_design_patterns.pipeline_v3.stage import AggregatorStage


class CountingAggregator(AggregatorStage):
    def __init__(self, **kwargs):
        super().__init__(name="agg", **kwargs)
        self.summary_out = self.add_output("summary", EventPacket)
        self.calls: list[dict] = []

    def aggregate(self, aligned):
        self.calls.append(dict(aligned))
        return {
            "summary": EventPacket(
                stream_id="agg",
                event_type="snapshot",
                metadata={"ports": sorted(aligned.keys())},
            )
        }


def _pose(stream_id: str, seq: int, ts: float, frame=None) -> PosePacket:
    return PosePacket(stream_id=stream_id, seq=seq, ts_capture=ts, frame=frame)


def test_port_for_creates_and_reuses():
    agg = CountingAggregator()
    p1 = agg.port_for("cam1")
    p2 = agg.port_for("cam1")
    assert p1 is p2
    assert "in-cam1" in agg.inputs


def test_aggregates_aligned_packets():
    agg = CountingAggregator(window_s=1.0)
    agg.port_for("cam1")
    agg.port_for("cam2")
    now = 1000.0
    out = agg.process({"in-cam1": _pose("cam1", 1, now), "in-cam2": _pose("cam2", 1, now + 0.1)})
    assert out is not None
    assert out["summary"].metadata["ports"] == ["in-cam1", "in-cam2"]


def test_misaligned_packets_not_aggregated():
    agg = CountingAggregator(window_s=0.2)
    now = 1000.0
    agg.process({"in-cam1": _pose("cam1", 1, now)})
    out = agg.process({"in-cam2": _pose("cam2", 1, now + 5.0)})  # far outside window
    assert out is None


def test_dedupe_same_combination_not_emitted_twice():
    """New data on one port must not re-emit the same aligned set."""
    agg = CountingAggregator(window_s=10.0)
    now = 1000.0
    out1 = agg.process({"in-cam1": _pose("cam1", 1, now)})
    assert out1 is not None
    # A tick with data for cam2 changes the combination → emit.
    out2 = agg.process({"in-cam2": _pose("cam2", 1, now)})
    assert out2 is not None
    # A tick that does not change the latest (port, seq) set → no emit.
    out3 = agg.process({"in-cam1": _pose("cam1", 1, now)})  # same seq re-delivered
    assert out3 is None
    assert len(agg.calls) == 2


def test_strip_frames_default_keeps_buffers_light():
    agg = CountingAggregator(window_s=10.0)
    frame = np.zeros((100, 100, 3), dtype=np.uint8)
    agg.process({"in-cam1": _pose("cam1", 1, 1000.0, frame=frame)})
    buffered = agg._buffers["in-cam1"][-1]
    assert buffered.frame is None  # heavy pixels dropped on ingest


def test_strip_frames_can_be_disabled():
    agg = CountingAggregator(window_s=10.0, strip_frames=False)
    frame = np.zeros((10, 10, 3), dtype=np.uint8)
    agg.process({"in-cam1": _pose("cam1", 1, 1000.0, frame=frame)})
    assert agg._buffers["in-cam1"][-1].frame is not None


def test_buffer_bounded():
    agg = CountingAggregator(window_s=10.0, max_buffer=5)
    for i in range(50):
        agg.process({"in-cam1": _pose("cam1", i, 1000.0 + i * 0.001)})
    assert len(agg._buffers["in-cam1"]) <= 5


def test_on_port_closed_frees_state():
    agg = CountingAggregator(window_s=10.0)
    agg.port_for("cam1")
    agg.process({"in-cam1": _pose("cam1", 1, 1000.0)})
    assert "in-cam1" in agg._buffers

    agg.on_port_closed("in-cam1")
    assert "in-cam1" not in agg._buffers
    assert "in-cam1" not in agg.inputs


def test_aggregator_accepts_generic_packets():
    agg = CountingAggregator(window_s=10.0)
    out = agg.process({"in-x": Packet(stream_id="x", seq=1, ts_capture=1000.0)})
    assert out is not None
