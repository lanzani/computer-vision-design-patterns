# -*- coding: utf-8 -*-
"""Synthetic frame source — demos and tests without a physical camera."""

from __future__ import annotations

import time

import numpy as np

from computer_vision_design_patterns.pipeline_v3.packet import FramePacket, Packet
from computer_vision_design_patterns.pipeline_v3.stage import ExecutorType, SourceStage


class SyntheticSource(SourceStage):
    """Emits generated frames at ``fps`` (paced by the runner, not by sleeping).

    Frames contain a moving vertical bar so downstream stages see changing
    content. Useful for demos, CI, and load testing.
    """

    def __init__(
        self,
        stream_id: str,
        fps: float = 15.0,
        shape: tuple[int, int, int] = (120, 160, 3),
        executor: ExecutorType = ExecutorType.THREAD,
        fill_value: int | None = None,
    ):
        super().__init__(name=f"synth-{stream_id}", executor=executor, target_fps=fps)
        self.stream_id = stream_id
        self.shape = shape
        self.fill_value = fill_value
        self.out = self.add_output("frames", FramePacket)

    def read(self) -> Packet | None:
        now = time.time()
        if self.fill_value is not None:
            frame = np.full(self.shape, self.fill_value, dtype=np.uint8)
        else:
            frame = np.zeros(self.shape, dtype=np.uint8)
            x = int(now * 40) % self.shape[1]
            frame[:, x : min(x + 4, self.shape[1])] = 255
        return FramePacket(
            stream_id=self.stream_id,
            seq=self.next_seq(),
            ts_capture=now,
            frame=frame,
        )
