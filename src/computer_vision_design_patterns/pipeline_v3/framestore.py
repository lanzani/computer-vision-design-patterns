# -*- coding: utf-8 -*-
"""Shared-memory frame transport (single-producer ring per channel).

``FrameWriter`` lives on the producer side of a cross-process edge: it lazily
allocates a ring of shared-memory slots sized from the first frame and writes
frames with a generation stamp before *and* after the pixel data.

``FrameReader`` lives on the consumer side: it attaches to slots by name and
copies frames out, verifying the generation stamp after the copy so torn or
stale frames are detected and dropped instead of silently corrupting output.

Slot layout: ``[8-byte generation][frame bytes][8-byte generation]``.
"""

from __future__ import annotations

import struct
import uuid
from multiprocessing import shared_memory

import numpy as np
from loguru import logger

from computer_vision_design_patterns.pipeline_v3.packet import FrameRef

_GEN_FMT = "<Q"
_GEN_SIZE = 8


class FrameWriter:
    """Single-producer ring of shared-memory frame slots.

    Not thread-safe: each writer belongs to exactly one channel, which
    serializes producers with its own lock.
    """

    def __init__(self, num_slots: int = 4, name: str | None = None):
        if num_slots < 1:
            raise ValueError("num_slots must be >= 1")
        self.num_slots = num_slots
        self.name = name or f"cvdp-{uuid.uuid4().hex[:12]}"
        self._slots: list[shared_memory.SharedMemory] = []
        self._generations: list[int] = [0] * num_slots
        self._next = 0
        self._shape: tuple[int, ...] | None = None
        self._dtype: np.dtype | None = None
        self._nbytes = 0
        self._closed = False

    def write(self, frame: np.ndarray) -> FrameRef | None:
        """Write ``frame`` into the next slot. Returns None if the frame does
        not match the ring's shape/dtype (caller falls back to pickling)."""
        if self._closed:
            return None

        if self._shape is None:
            self._allocate(frame)
        elif frame.shape != self._shape or frame.dtype != self._dtype:
            return None

        idx = self._next % self.num_slots
        self._next += 1
        self._generations[idx] += 1
        generation = self._generations[idx]

        shm = self._slots[idx]
        struct.pack_into(_GEN_FMT, shm.buf, 0, generation)
        view = np.ndarray(self._shape, dtype=self._dtype, buffer=shm.buf, offset=_GEN_SIZE)
        np.copyto(view, frame)
        struct.pack_into(_GEN_FMT, shm.buf, _GEN_SIZE + self._nbytes, generation)

        return FrameRef(
            shm_name=shm.name,
            shape=self._shape,
            dtype=str(self._dtype),
            generation=generation,
        )

    def _allocate(self, frame: np.ndarray) -> None:
        self._shape = tuple(frame.shape)
        self._dtype = frame.dtype
        self._nbytes = int(frame.nbytes)
        size = _GEN_SIZE * 2 + self._nbytes
        for i in range(self.num_slots):
            self._slots.append(shared_memory.SharedMemory(create=True, size=size, name=f"{self.name}-{i}"))

    def close(self) -> None:
        """Close and unlink all slots. Only the writer (creator) unlinks."""
        if self._closed:
            return
        self._closed = True
        for shm in self._slots:
            try:
                shm.close()
            except Exception:
                pass
            try:
                shm.unlink()
            except Exception:
                pass
        self._slots.clear()


class FrameReader:
    """Consumer-side view onto frames published by a FrameWriter.

    Attachments are cached by shared-memory name (slot names are stable for
    the lifetime of a channel). ``read_copy`` never returns a live view — the
    frame is copied out and validated, so the caller owns the result.
    """

    def __init__(self):
        self._cache: dict[str, shared_memory.SharedMemory] = {}
        self._closed = False

    def read_copy(self, ref: FrameRef) -> np.ndarray | None:
        """Copy the referenced frame out of shared memory.

        Returns None if the slot is gone, stale, or was overwritten during the
        copy (torn) — callers treat this as a dropped frame.
        """
        if self._closed:
            return None

        shm = self._cache.get(ref.shm_name)
        if shm is None:
            try:
                shm = shared_memory.SharedMemory(name=ref.shm_name)
            except (FileNotFoundError, OSError):
                return None
            self._cache[ref.shm_name] = shm

        dtype = np.dtype(ref.dtype)
        nbytes = int(np.prod(ref.shape)) * dtype.itemsize
        if shm.size < _GEN_SIZE * 2 + nbytes:
            logger.warning(f"FrameRef {ref.shm_name} does not fit slot size {shm.size}")
            return None

        (head,) = struct.unpack_from(_GEN_FMT, shm.buf, 0)
        if head != ref.generation:
            return None  # stale: slot was reused

        view = np.ndarray(ref.shape, dtype=dtype, buffer=shm.buf, offset=_GEN_SIZE)
        frame = np.array(view, copy=True)

        (foot,) = struct.unpack_from(_GEN_FMT, shm.buf, _GEN_SIZE + nbytes)
        if foot != ref.generation:
            return None  # torn: writer overwrote the slot mid-copy

        return frame

    def close(self) -> None:
        """Close attachments (never unlinks — the writer owns the memory)."""
        if self._closed:
            return
        self._closed = True
        for shm in self._cache.values():
            try:
                shm.close()
            except Exception:
                pass
        self._cache.clear()
