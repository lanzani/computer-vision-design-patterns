# -*- coding: utf-8 -*-
"""OpenCV camera / video file source with reconnect on failure."""

from __future__ import annotations

import time
from typing import Any

from loguru import logger

from computer_vision_design_patterns.pipeline_v3.packet import FramePacket, Packet
from computer_vision_design_patterns.pipeline_v3.stage import ExecutorType, SourceStage


class CameraSource(SourceStage):
    """OpenCV camera / RTSP / video file source.

    ``read()`` never sleeps: on failure it releases the capture and returns
    None, and the runner applies stop-aware exponential backoff before the
    next attempt (so a dead camera neither busy-spins nor blocks shutdown).
    """

    def __init__(
        self,
        stream_id: str,
        source: int | str = 0,
        executor: ExecutorType = ExecutorType.THREAD,
        target_fps: float | None = None,
        width: int | None = None,
        height: int | None = None,
    ):
        super().__init__(
            name=f"camera-{stream_id}",
            executor=executor,
            target_fps=target_fps,
            read_backoff_s=0.1,
            max_read_backoff_s=3.0,
        )
        self.stream_id = stream_id
        self.source = source
        self.width = width
        self.height = height
        self._cap: Any = None
        self.out = self.add_output("frames", FramePacket)

    def setup(self) -> None:
        self._open()

    def teardown(self) -> None:
        self._release()

    def _open(self) -> None:
        import cv2

        self._release()
        cap = cv2.VideoCapture(self.source)
        if self.width is not None:
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
        if self.height is not None:
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
        if not cap.isOpened():
            logger.warning(f"CameraSource {self.stream_id!r}: failed to open {self.source!r}")
            cap.release()
            return
        self._cap = cap

    def _release(self) -> None:
        if self._cap is not None:
            try:
                self._cap.release()
            except Exception:
                pass
            self._cap = None

    def read(self) -> Packet | None:
        if self._cap is None:
            self._open()
            if self._cap is None:
                return None

        ok, frame = self._cap.read()
        if not ok or frame is None:
            logger.warning(f"CameraSource {self.stream_id!r}: read failed — will reconnect")
            self._release()
            return None

        return FramePacket(
            stream_id=self.stream_id,
            seq=self.next_seq(),
            ts_capture=time.time(),
            frame=frame,
        )
