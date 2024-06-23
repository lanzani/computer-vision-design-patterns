# -*- coding: utf-8 -*-
from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np

from computer_vision_design_patterns.pipeline import ProcessStage1to1, ThreadStage1to1
import multiprocessing as mp
from computer_vision_design_patterns.pipeline import Payload
from loguru import logger


@dataclass(frozen=True, eq=False, slots=True, kw_only=True)
class VideoStreamOutput(Payload):
    frame: np.ndarray | None


class SimpleStreamStage(ProcessStage1to1):
    def __init__(
        self,
        key: str,
        source,
        output_maxsize: int | None = None,
        queue_timeout: int | None = None,
        control_queue: mp.Queue | None = None,
    ):
        super().__init__(key, output_maxsize, queue_timeout, control_queue)

        self.source = source
        self._cap = None

    def process(self, payload: Payload | None) -> VideoStreamOutput | None:
        ret, frame = self._cap.read()
        if not ret:
            return None

        return VideoStreamOutput(frame=frame)

    def run(self) -> None:
        try:
            self._cap = cv2.VideoCapture(self.source)

            while self._cap.isOpened():
                processed_payload = self.process(None)
                self.put_to_right(processed_payload)

        except KeyboardInterrupt:
            logger.info(f"SimpleStreamStage {self.key} stopped.")

        self._cap.release()
        exit(0)
