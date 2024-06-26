# -*- coding: utf-8 -*-
from __future__ import annotations

import cv2

from computer_vision_design_patterns.pipeline import Stage1to1, ProcessStage
import multiprocessing as mp
from computer_vision_design_patterns.pipeline import Payload
from loguru import logger

executor = ProcessStage


class VideoSink(Stage1to1, executor):
    def __init__(
        self,
        key: str,
        output_maxsize: int | None = None,
        queue_timeout: int | None = None,
        control_queue: mp.Queue | None = None,
    ):
        Stage1to1.__init__(self, key, output_maxsize, queue_timeout, control_queue)
        executor.__init__(self, name=f"VideoSink {key}")

    def process(self, payload: Payload | None):
        frame = payload.frame
        if frame is None:
            return

        cv2.imshow(f"VideoSink {self.key}", frame)
        user_input = cv2.waitKey(1) & 0xFF

        if user_input == ord("q"):
            cv2.destroyAllWindows()
            exit(0)

    def run(self) -> None:
        while not self.stop_event.is_set():
            payload = self.get_from_left()
            if payload is None:
                logger.warning("No payload")
                continue
            self.process(payload)

        cv2.destroyAllWindows()
        logger.info("VideoSink stopped")
        exit(0)
