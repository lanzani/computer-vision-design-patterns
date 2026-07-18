# -*- coding: utf-8 -*-
"""Tests for pipeline_v3 packet types."""

from __future__ import annotations

import pickle
import time

import pytest

from computer_vision_design_patterns.pipeline_v3.packet import (
    SENTINEL,
    EventPacket,
    FramePacket,
    FrameRef,
    Packet,
    PosePacket,
)


def test_packet_defaults():
    p = Packet(stream_id="cam1")
    assert p.stream_id == "cam1"
    assert p.seq == 0
    assert isinstance(p.ts_capture, float)
    assert p.ts_capture <= time.time()


def test_frame_packet_with_ref():
    ref = FrameRef(shm_name="cvdp-abc-0", shape=(10, 10, 3), dtype="uint8", generation=1)
    fp = FramePacket(stream_id="s", seq=3, frame_ref=ref)
    assert fp.frame is None
    assert fp.frame_ref.shm_name == "cvdp-abc-0"


def test_pose_and_event():
    pose = PosePacket(stream_id="s", keypoints=((1.0, 2.0, 0.9),), bbox=(0, 0, 10, 10))
    assert len(pose.keypoints) == 1
    ev = EventPacket(stream_id="s", event_type="fall", confidence=0.8, metadata={"x": 1})
    assert ev.event_type == "fall"


def test_packets_are_frozen():
    p = Packet(stream_id="s")
    with pytest.raises(Exception):
        p.seq = 99  # type: ignore[misc]


def test_packet_pickles():
    p = PosePacket(stream_id="s", seq=4, keypoints=((1.0, 2.0, 0.5),))
    restored = pickle.loads(pickle.dumps(p))
    assert restored == p or (restored.stream_id == "s" and restored.seq == 4)


def test_sentinel_identity_and_not_instantiable():
    assert pickle.loads(pickle.dumps(SENTINEL)) is SENTINEL
    with pytest.raises(TypeError):
        SENTINEL()
