# -*- coding: utf-8 -*-
"""Packet types carried between pipeline stages."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any


class SENTINEL:
    """Marker signalling channel close / drain.

    This is a *class* (not an instance) so it pickles by reference and keeps
    its identity across process boundaries — ``item is SENTINEL`` works in a
    child process, which would not be true for a plain ``object()`` instance.
    """

    def __new__(cls):  # pragma: no cover - defensive
        raise TypeError("SENTINEL is a marker and must not be instantiated")


@dataclass(frozen=True, slots=True)
class Packet:
    """Base data unit passed between stages.

    ``stream_id`` travels inside the packet so routing no longer depends on
    shared string keys between producer and consumer.
    """

    stream_id: str
    seq: int = 0
    ts_capture: float = field(default_factory=time.time)


@dataclass(frozen=True, slots=True)
class FrameRef:
    """Reference to a frame stored in shared memory (cross-process edges).

    ``shm_name`` identifies the shared-memory slot; consumers attach by name.
    ``generation`` guards against slot reuse: the writer embeds it before and
    after the pixel data, so readers detect stale or torn frames.
    """

    shm_name: str
    shape: tuple[int, ...]
    dtype: str
    generation: int


@dataclass(frozen=True, slots=True)
class FramePacket(Packet):
    """Video frame packet.

    ``frame`` holds the numpy array on thread-thread edges. On cross-process
    edges the channel transparently swaps it for a shared-memory ``frame_ref``
    on the producer side and restores ``frame`` on the consumer side — stages
    always see a plain numpy array.
    """

    frame: Any = None  # np.ndarray | None
    frame_ref: FrameRef | None = None


@dataclass(frozen=True, slots=True)
class PosePacket(Packet):
    """Pose / keypoint detection result for a single stream."""

    keypoints: tuple[tuple[float, float, float], ...] = ()
    """(x, y, confidence) triples."""

    bbox: tuple[float, float, float, float] | None = None
    """(x, y, w, h) if available."""

    frame: Any = None  # np.ndarray | None
    frame_ref: FrameRef | None = None


@dataclass(frozen=True, slots=True)
class EventPacket(Packet):
    """High-level event emitted by detection / aggregation stages."""

    event_type: str = ""
    confidence: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)
