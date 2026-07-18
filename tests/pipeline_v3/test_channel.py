# -*- coding: utf-8 -*-
"""Tests for pipeline_v3 channels: policies, sentinel drain, drop accounting."""

from __future__ import annotations

import pickle
import queue

import pytest

from computer_vision_design_patterns.pipeline_v3.channel import (
    ChannelClosed,
    OverflowPolicy,
    ProcessChannel,
    ThreadChannel,
    make_channel,
)
from computer_vision_design_patterns.pipeline_v3.packet import SENTINEL, Packet


def test_put_get_roundtrip():
    ch = ThreadChannel(maxsize=2, policy=OverflowPolicy.BLOCK)
    assert ch.put(Packet(stream_id="s1", seq=1)) is True
    got = ch.get(timeout=0.5)
    assert got.seq == 1
    assert got.stream_id == "s1"


def test_get_nowait():
    ch = ThreadChannel(maxsize=2, policy=OverflowPolicy.BLOCK)
    with pytest.raises(queue.Empty):
        ch.get_nowait()
    ch.put(Packet(stream_id="s", seq=7))
    assert ch.get_nowait().seq == 7


def test_latest_only_keeps_newest_and_counts_drops():
    ch = ThreadChannel(policy=OverflowPolicy.LATEST_ONLY)
    ch.put(Packet(stream_id="s", seq=1))
    ch.put(Packet(stream_id="s", seq=2))
    ch.put(Packet(stream_id="s", seq=3))
    assert ch.get(timeout=0.5).seq == 3
    with pytest.raises(queue.Empty):
        ch.get_nowait()  # only the newest item was kept
    assert ch.drops == 2  # seq 1 and 2 were conflated away


def test_drop_oldest():
    ch = ThreadChannel(maxsize=2, policy=OverflowPolicy.DROP_OLDEST)
    ch.put(Packet(stream_id="s", seq=1))
    ch.put(Packet(stream_id="s", seq=2))
    ch.put(Packet(stream_id="s", seq=3))  # drops seq=1
    assert {ch.get(timeout=0.5).seq, ch.get(timeout=0.5).seq} == {2, 3}
    assert ch.drops == 1


def test_block_timeout_returns_false():
    ch = ThreadChannel(maxsize=1, policy=OverflowPolicy.BLOCK, put_timeout=0.05)
    assert ch.put(Packet(stream_id="s", seq=1)) is True
    assert ch.put(Packet(stream_id="s", seq=2), timeout=0.05) is False


def test_sentinel_after_drain_on_close():
    ch = ThreadChannel(maxsize=2, policy=OverflowPolicy.BLOCK)
    ch.put(Packet(stream_id="s", seq=1))
    ch.close()
    # Pending items are drained first, then SENTINEL.
    assert ch.get(timeout=0.5).seq == 1
    assert ch.get(timeout=0.5) is SENTINEL
    assert ch.closed


def test_sentinel_wakes_multiple_consumers():
    ch = ThreadChannel(maxsize=2, policy=OverflowPolicy.BLOCK)
    ch.close()
    # SENTINEL is re-queued so every consumer observes the close.
    assert ch.get(timeout=0.5) is SENTINEL
    assert ch.get(timeout=0.5) is SENTINEL


def test_put_on_closed_raises():
    ch = ThreadChannel()
    ch.close()
    with pytest.raises(ChannelClosed):
        ch.put(Packet(stream_id="s", seq=1))


def test_get_timeout_raises_empty_when_open():
    ch = ThreadChannel()
    with pytest.raises(queue.Empty):
        ch.get(timeout=0.01)


def test_unbounded_rejected():
    with pytest.raises(ValueError):
        ThreadChannel(maxsize=0, policy=OverflowPolicy.BLOCK)


def test_make_channel_picks_backend():
    assert isinstance(make_channel(cross_process=False), ThreadChannel)
    assert isinstance(make_channel(cross_process=True), ProcessChannel)


def test_sentinel_survives_pickle_with_identity():
    # SENTINEL must keep identity across process boundaries (it is a class,
    # pickled by reference). A plain object() instance would fail this.
    assert pickle.loads(pickle.dumps(SENTINEL)) is SENTINEL


def test_process_channel_basic_roundtrip():
    ch = ProcessChannel(maxsize=2, policy=OverflowPolicy.BLOCK)
    ch.put(Packet(stream_id="s", seq=5))
    assert ch.get(timeout=1.0).seq == 5
    ch.close()
    assert ch.get(timeout=1.0) is SENTINEL


def test_process_channel_frame_transport_same_process():
    """Frames are swapped to shared memory on put and restored on get."""
    import numpy as np

    from computer_vision_design_patterns.pipeline_v3.packet import FramePacket

    ch = ProcessChannel(maxsize=2, policy=OverflowPolicy.BLOCK)
    frame = np.arange(2 * 3 * 3, dtype=np.uint8).reshape(2, 3, 3)
    ch.put(FramePacket(stream_id="s", seq=1, frame=frame))

    got = ch.get(timeout=1.0)
    assert got.frame_ref is None  # restored transparently
    np.testing.assert_array_equal(got.frame, frame)

    ch.release_consumer_resources()
    ch.release_producer_resources()
