# -*- coding: utf-8 -*-
"""Bounded channels with overflow policies, sentinel drain, and transparent
shared-memory frame transport on cross-process edges."""

from __future__ import annotations

import dataclasses
import multiprocessing as mp
import queue
import threading
from enum import Enum, auto
from typing import Any

from computer_vision_design_patterns.pipeline_v3.packet import SENTINEL


class OverflowPolicy(Enum):
    """What to do when a bounded channel is full."""

    BLOCK = auto()
    """Block the producer until space is available (or timeout)."""

    DROP_OLDEST = auto()
    """Drop the oldest item, then insert the new one."""

    LATEST_ONLY = auto()
    """Conflating buffer of depth 1 — always keep the newest item (default for video)."""


class ChannelClosed(Exception):
    """Raised when putting on a closed channel."""


class Channel:
    """Bounded, closable channel between two stages.

    All overflow, sentinel-drain, and encode/decode behavior lives here.
    Concrete subclasses (ThreadChannel, ProcessChannel) supply the backing
    queue and lock, and may override the state/payload hooks.
    """

    def __init__(
        self,
        maxsize: int = 1,
        policy: OverflowPolicy = OverflowPolicy.LATEST_ONLY,
        put_timeout: float | None = 0.1,
        get_timeout: float | None = 0.1,
    ):
        if policy == OverflowPolicy.LATEST_ONLY:
            maxsize = 1
        if maxsize < 1:
            raise ValueError("Channel maxsize must be >= 1 (unbounded queues are not allowed)")

        self._maxsize = maxsize
        self._policy = policy
        self._put_timeout = put_timeout
        self._get_timeout = get_timeout
        self._drops = 0
        self._closed = False
        # Set by subclasses:
        self._queue: Any = None
        self._lock: Any = None

    # -- state hooks (overridden by ProcessChannel for cross-process state) --

    @property
    def closed(self) -> bool:
        """Whether the channel has been closed."""
        return self._closed

    @property
    def drops(self) -> int:
        """Number of items dropped due to overflow policy or stale frames."""
        return self._drops

    def _mark_closed(self) -> None:
        self._closed = True

    def _count_drop(self) -> None:
        self._drops += 1

    # -- payload hooks (overridden by ProcessChannel for frame transport) ----

    def _encode(self, item: Any) -> Any:
        return item

    def _decode(self, item: Any) -> Any:
        """Return the decoded item, or None if it is stale and must be skipped."""
        return item

    def release_producer_resources(self) -> None:
        """Free producer-side resources (e.g. shared-memory writer)."""

    def release_consumer_resources(self) -> None:
        """Free consumer-side resources (e.g. shared-memory attachments)."""

    # -- API ------------------------------------------------------------------

    def put(self, item: Any, timeout: float | None = None) -> bool:
        """Put an item. Returns False if dropped or timed out under BLOCK."""
        with self._lock:
            if self.closed:
                raise ChannelClosed("Cannot put on a closed channel")

            item = self._encode(item)
            if timeout is None:
                timeout = self._put_timeout

            if self._policy == OverflowPolicy.BLOCK:
                try:
                    self._queue.put(item, timeout=timeout)
                    return True
                except queue.Full:
                    return False

            if self._policy == OverflowPolicy.LATEST_ONLY:
                self._evict_oldest()  # always replace with the newest item
            else:  # DROP_OLDEST: make room only when full
                try:
                    self._queue.put_nowait(item)
                    return True
                except queue.Full:
                    self._evict_oldest()

            try:
                self._queue.put_nowait(item)
                return True
            except queue.Full:
                self._count_drop()
                return False

    def get(self, timeout: float | None = None) -> Any:
        """Get an item. Returns SENTINEL when closed and drained. Raises queue.Empty on timeout."""
        return self._get(timeout, block=True)

    def get_nowait(self) -> Any:
        """Non-blocking get. Raises queue.Empty when nothing is available."""
        return self._get(None, block=False)

    def close(self) -> None:
        """Close the channel and wake blocked consumers with SENTINEL.

        Pending items are never dropped: consumers drain them first, then see
        closed-on-empty and receive SENTINEL.
        """
        with self._lock:
            if self.closed:
                return
            self._mark_closed()
        try:
            self._queue.put_nowait(SENTINEL)
        except queue.Full:
            pass

    # -- internals ---------------------------------------------------------------

    def _evict_oldest(self) -> None:
        try:
            old = self._queue.get_nowait()
            if old is not SENTINEL:
                self._count_drop()
        except queue.Empty:
            pass

    def _get(self, timeout: float | None, block: bool) -> Any:
        if timeout is None:
            timeout = self._get_timeout

        while True:
            try:
                item = self._queue.get(timeout=timeout) if block else self._queue.get_nowait()
            except queue.Empty:
                if self.closed:
                    return SENTINEL
                raise

            if item is SENTINEL:
                # Re-queue so other waiters also observe the close.
                try:
                    self._queue.put_nowait(SENTINEL)
                except queue.Full:
                    pass
                return SENTINEL

            decoded = self._decode(item)
            if decoded is None:
                # Stale/torn frame — treat as a drop and keep looking.
                self._count_drop()
                if not block:
                    raise queue.Empty
                continue
            return decoded


class ThreadChannel(Channel):
    """Channel backed by ``queue.Queue`` — for thread ↔ thread edges."""

    def __init__(
        self,
        maxsize: int = 1,
        policy: OverflowPolicy = OverflowPolicy.LATEST_ONLY,
        put_timeout: float | None = 0.1,
        get_timeout: float | None = 0.1,
    ):
        super().__init__(maxsize=maxsize, policy=policy, put_timeout=put_timeout, get_timeout=get_timeout)
        self._queue = queue.Queue(maxsize=self._maxsize)
        self._lock = threading.Lock()


class ProcessChannel(Channel):
    """Channel backed by ``multiprocessing.Queue`` — for cross-process edges.

    ``FramePacket``-like payloads (anything with ``frame`` / ``frame_ref``
    fields) are transported through shared memory instead of pickling: the
    producer side swaps the numpy frame for a ``FrameRef``; the consumer side
    copies the frame back out. Stages never see the difference.
    """

    def __init__(
        self,
        maxsize: int = 1,
        policy: OverflowPolicy = OverflowPolicy.LATEST_ONLY,
        put_timeout: float | None = 0.1,
        get_timeout: float | None = 0.1,
        ctx: mp.context.BaseContext | None = None,
    ):
        super().__init__(maxsize=maxsize, policy=policy, put_timeout=put_timeout, get_timeout=get_timeout)
        ctx = ctx or mp.get_context("spawn")
        self._queue = ctx.Queue(maxsize=self._maxsize)
        self._lock = ctx.Lock()
        self._closed_flag = ctx.Value("b", 0)
        self._drops_counter = ctx.Value("i", 0)
        # Lazily created, process-local (never pickled):
        self._frame_writer = None
        self._frame_reader = None

    def __getstate__(self):
        state = self.__dict__.copy()
        state["_frame_writer"] = None
        state["_frame_reader"] = None
        return state

    # -- cross-process state --------------------------------------------------

    @property
    def closed(self) -> bool:
        return bool(self._closed_flag.value)

    @property
    def drops(self) -> int:
        return int(self._drops_counter.value)

    def _mark_closed(self) -> None:
        self._closed_flag.value = 1

    def _count_drop(self) -> None:
        with self._drops_counter.get_lock():
            self._drops_counter.value += 1

    # -- frame transport --------------------------------------------------------

    def _encode(self, item: Any) -> Any:
        frame = getattr(item, "frame", None)
        if frame is None or not hasattr(item, "frame_ref"):
            return item
        import numpy as np

        if not isinstance(frame, np.ndarray):
            return item

        if self._frame_writer is None:
            from computer_vision_design_patterns.pipeline_v3.framestore import FrameWriter

            # maxsize refs in queue + 1 being written + 1 being read.
            self._frame_writer = FrameWriter(num_slots=self._maxsize + 2)

        ref = self._frame_writer.write(frame)
        if ref is None:
            return item  # shape/dtype mismatch → pickle fallback
        return dataclasses.replace(item, frame=None, frame_ref=ref)

    def _decode(self, item: Any) -> Any:
        ref = getattr(item, "frame_ref", None)
        if ref is None:
            return item

        if self._frame_reader is None:
            from computer_vision_design_patterns.pipeline_v3.framestore import FrameReader

            self._frame_reader = FrameReader()

        frame = self._frame_reader.read_copy(ref)
        if frame is None:
            return None  # stale/torn → dropped by _get
        return dataclasses.replace(item, frame=frame, frame_ref=None)

    def release_producer_resources(self) -> None:
        if self._frame_writer is not None:
            self._frame_writer.close()
            self._frame_writer = None

    def release_consumer_resources(self) -> None:
        if self._frame_reader is not None:
            self._frame_reader.close()
            self._frame_reader = None


def make_channel(
    cross_process: bool,
    maxsize: int = 1,
    policy: OverflowPolicy = OverflowPolicy.LATEST_ONLY,
    ctx: mp.context.BaseContext | None = None,
) -> Channel:
    """Factory: pick ThreadChannel or ProcessChannel based on edge type."""
    if cross_process:
        return ProcessChannel(maxsize=maxsize, policy=policy, ctx=ctx)
    return ThreadChannel(maxsize=maxsize, policy=policy)
