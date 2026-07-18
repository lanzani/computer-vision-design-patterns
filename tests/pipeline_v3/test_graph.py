# -*- coding: utf-8 -*-
"""Tests for pipeline_v3 graph validation."""

from __future__ import annotations

import pytest

from computer_vision_design_patterns.pipeline_v3.graph import GraphValidationError, PipelineGraph
from computer_vision_design_patterns.pipeline_v3.packet import FramePacket, Packet, PosePacket
from computer_vision_design_patterns.pipeline_v3.stage import Stage


class _Passthrough(Stage):
    def __init__(self, name: str, in_type=FramePacket, out_type=FramePacket):
        super().__init__(name=name)
        self.inp = self.add_input("in", in_type)
        self.out = self.add_output("out", out_type)

    def process(self, inputs):
        return {"out": inputs.get("in")}


class _Source(Stage):
    def __init__(self, name: str = "src", out_type=FramePacket):
        super().__init__(name=name)
        self.out = self.add_output("out", out_type)

    def process(self, inputs):
        return None


class _Sink(Stage):
    def __init__(self, name: str = "sink", in_type=FramePacket):
        super().__init__(name=name)
        self.inp = self.add_input("in", in_type)

    def process(self, inputs):
        return None


def test_valid_linear_graph():
    g = PipelineGraph()
    src, mid, sink = _Source(), _Passthrough("mid"), _Sink()
    for s in (src, mid, sink):
        g.add_stage(s)
    g.connect(src.out, mid.inp)
    g.connect(mid.out, sink.inp)
    g.validate()
    assert [s.name for s in g.topological_order()] == ["src", "mid", "sink"]


def test_type_mismatch_rejected():
    g = PipelineGraph()
    src = _Source(out_type=FramePacket)
    sink = _Sink(in_type=PosePacket)  # expects PosePacket, would get FramePacket
    g.add_stage(src)
    g.add_stage(sink)
    with pytest.raises(GraphValidationError, match="type mismatch"):
        g.connect(src.out, sink.inp)


def test_subclass_into_base_port_allowed():
    """A source emitting a Packet subclass may feed a port accepting Packet."""
    g = PipelineGraph()
    src = _Source(out_type=PosePacket)
    sink = _Sink(in_type=Packet)
    g.add_stage(src)
    g.add_stage(sink)
    g.connect(src.out, sink.inp)  # no raise
    g.validate()


def test_base_into_subclass_port_rejected():
    """A source emitting base Packet must NOT feed a port that requires a subclass."""
    g = PipelineGraph()
    src = _Source(out_type=Packet)
    sink = _Sink(in_type=PosePacket)
    g.add_stage(src)
    g.add_stage(sink)
    with pytest.raises(GraphValidationError, match="type mismatch"):
        g.connect(src.out, sink.inp)


def test_duplicate_input_edge_rejected():
    """Two producers into the same input port must fail loudly, not silently drop."""
    g = PipelineGraph()
    src1, src2, sink = _Source("src1"), _Source("src2"), _Sink()
    for s in (src1, src2, sink):
        g.add_stage(s)
    g.connect(src1.out, sink.inp)
    with pytest.raises(GraphValidationError, match="already has an incoming edge"):
        g.connect(src2.out, sink.inp)


def test_dangling_output_allowed():
    """Unconnected outputs are fine — their packets are simply dropped."""
    g = PipelineGraph()
    src, mid = _Source(), _Passthrough("mid")
    g.add_stage(src)
    g.add_stage(mid)
    g.connect(src.out, mid.inp)
    g.validate()  # mid.out is dangling — no raise


def test_dangling_input_rejected():
    g = PipelineGraph()
    g.add_stage(_Sink())
    with pytest.raises(GraphValidationError, match="Dangling input"):
        g.validate()


def test_cycle_detected():
    g = PipelineGraph()
    a, b = _Passthrough("a"), _Passthrough("b")
    g.add_stage(a)
    g.add_stage(b)
    g.connect(a.out, b.inp)
    g.connect(b.out, a.inp)
    with pytest.raises(GraphValidationError, match="cycle"):
        g.validate()


def test_duplicate_stage_name():
    g = PipelineGraph()
    g.add_stage(_Source("src"))
    with pytest.raises(GraphValidationError, match="Duplicate"):
        g.add_stage(_Source("src"))


def test_stream_tagging_and_remove():
    g = PipelineGraph()
    src, sink = _Source("cam1"), _Sink("sink1")
    g.add_stage(src, stream_id="s1")
    g.add_stage(sink, stream_id="s1")
    g.connect(src.out, sink.inp, stream_id="s1")
    assert g.has_stream("s1")
    assert len(g.stages_for_stream("s1")) == 2
    removed_stages, removed_edges = g.remove_stream("s1")
    assert len(removed_stages) == 2
    assert len(removed_edges) == 1
    assert g.stages == []
    assert not g.has_stream("s1")


def test_remove_stream_drops_attach_edges():
    """Edges from a removed stream's stages to shared stages must go too."""
    g = PipelineGraph()
    shared_sink = _Sink("shared")
    src = _Source("cam1")
    g.add_stage(shared_sink)
    g.add_stage(src, stream_id="s1")
    g.connect(src.out, shared_sink.inp, stream_id="s1")
    g.remove_stream("s1")
    assert g.edges == []
    assert [s.name for s in g.stages] == ["shared"]
