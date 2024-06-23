# -*- coding: utf-8 -*-
from __future__ import annotations

import time
from dataclasses import dataclass

import cv2
import numpy as np

from computer_vision_design_patterns.pipeline import Stage1to1, ProcessStage, ThreadStage

import multiprocessing as mp
from computer_vision_design_patterns.pipeline import Payload
from loguru import logger


@dataclass(frozen=True, eq=False, slots=True, kw_only=True)
class VideoStreamOutput(Payload):
    frame: np.ndarray | None


executor = ProcessStage


class SimpleStreamStage(Stage1to1, executor):
    def __init__(
        self,
        key: str,
        source,
        output_maxsize: int | None = None,
        queue_timeout: int | None = None,
        control_queue: mp.Queue | None = None,
    ):
        Stage1to1.__init__(self, key, output_maxsize, queue_timeout, control_queue)
        executor.__init__(self)

        self.source = source
        self._cap = None

    def process(self, payload: Payload | None) -> VideoStreamOutput | None:
        ret, frame = self._cap.read()
        if not ret:
            return None

        return VideoStreamOutput(frame=frame)

    def run(self) -> None:
        self._cap = cv2.VideoCapture(self.source)

        while not self.stop_event.is_set():
            if not self._cap.isOpened():
                break

            processed_payload = self.process(None)
            self.put_to_right(processed_payload)

        self._cap.release()
        logger.info(f"SimpleStreamStage {self.key} stopped.")
        exit(0)
