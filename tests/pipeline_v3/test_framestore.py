# -*- coding: utf-8 -*-
"""Tests for the shared-memory frame transport (FrameWriter / FrameReader)."""

from __future__ import annotations

import struct

import numpy as np
import pytest

from computer_vision_design_patterns.pipeline_v3.framestore import FrameReader, FrameWriter
from computer_vision_design_patterns.pipeline_v3.packet import FrameRef


@pytest.fixture()
def writer_reader():
    writer = FrameWriter(num_slots=3)
    reader = FrameReader()
    yield writer, reader
    reader.close()
    writer.close()


def test_write_read_roundtrip(writer_reader):
    writer, reader = writer_reader
    frame = np.arange(8 * 12 * 3, dtype=np.uint8).reshape(8, 12, 3)
    ref = writer.write(frame)
    assert ref is not None
    out = reader.read_copy(ref)
    np.testing.assert_array_equal(out, frame)


def test_read_copy_is_owned(writer_reader):
    writer, reader = writer_reader
    frame = np.full((4, 4, 3), 7, dtype=np.uint8)
    ref = writer.write(frame)
    out = reader.read_copy(ref)
    out[0, 0] = 0  # mutating the copy must not affect the slot
    again = reader.read_copy(ref)
    assert again[0, 0].tolist() == [7, 7, 7]


def test_stale_ref_detected(writer_reader):
    writer, reader = writer_reader
    ref1 = writer.write(np.zeros((4, 4), dtype=np.uint8))
    # Cycle the ring until slot 0 is reused.
    for _ in range(writer.num_slots):
        ref_new = writer.write(np.ones((4, 4), dtype=np.uint8))
    assert ref_new.shm_name == ref1.shm_name  # same slot, new generation
    assert reader.read_copy(ref1) is None  # stale detected
    np.testing.assert_array_equal(reader.read_copy(ref_new), np.ones((4, 4), dtype=np.uint8))


def test_torn_read_detected(writer_reader):
    """A mismatching footer generation (writer overwrote mid-copy) is rejected."""
    writer, reader = writer_reader
    frame = np.zeros((4, 4), dtype=np.uint8)
    ref = writer.write(frame)
    # Corrupt the footer to simulate a torn write.
    shm = writer._slots[0]
    struct.pack_into("<Q", shm.buf, 8 + frame.nbytes, ref.generation + 999)
    assert reader.read_copy(ref) is None


def test_shape_change_falls_back(writer_reader):
    writer, _ = writer_reader
    assert writer.write(np.zeros((4, 4), dtype=np.uint8)) is not None
    # Different shape → None → caller pickles instead. No crash.
    assert writer.write(np.zeros((8, 8), dtype=np.uint8)) is None


def test_missing_slot_returns_none():
    reader = FrameReader()
    ref = FrameRef(shm_name="cvdp-does-not-exist-0", shape=(2, 2), dtype="uint8", generation=1)
    assert reader.read_copy(ref) is None
    reader.close()


def test_writer_close_idempotent():
    writer = FrameWriter(num_slots=2)
    writer.write(np.zeros((2, 2), dtype=np.uint8))
    writer.close()
    writer.close()  # no error
    assert writer.write(np.zeros((2, 2), dtype=np.uint8)) is None
