# -*- coding: utf-8 -*-
from __future__ import annotations

import cv2

from computer_vision_design_patterns.pipeline import ProcessStage1to1, ThreadStage1to1
import multiprocessing as mp
from computer_vision_design_patterns.pipeline import Payload
from loguru import logger


class VideoSink(ProcessStage1to1):
    def __init__(
        self,
        key: str,
        output_maxsize: int | None = None,
        queue_timeout: int | None = None,
        control_queue: mp.Queue | None = None,
    ):
        super().__init__(key, output_maxsize, queue_timeout, control_queue)

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
        try:
            while True:
                payload = self.get_from_left()
                if payload is None:
                    logger.warning("No payload")
                    continue
                self.process(payload)

        except KeyboardInterrupt:
            pass
        logger.info("VideoSink stopped")

        cv2.destroyAllWindows()
        exit(0)
