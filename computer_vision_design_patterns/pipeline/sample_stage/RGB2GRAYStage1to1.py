# -*- coding: utf-8 -*-
from __future__ import annotations

import cv2

from computer_vision_design_patterns.pipeline import ProcessStage, Payload, Stage1to1
import multiprocessing as mp
from loguru import logger

from computer_vision_design_patterns.pipeline.sample_stage.SimpleStreamStage import VideoStreamOutput

executor = ProcessStage


class RGB2GRAYStage1to1(Stage1to1, executor):
    def __init__(
        self,
        key: str,
        output_maxsize: int | None = None,
        queue_timeout: int | None = None,
        control_queue: mp.Queue | None = None,
    ):
        Stage1to1.__init__(self, key, output_maxsize, queue_timeout, control_queue)
        executor.__init__(self, name=f"RGB2GRAYStage {key}")

    def process(self, payload: Payload):
        frame = payload.frame
        if frame is None:
            return

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        processed_payload = VideoStreamOutput(timestamp=payload.timestamp, frame=gray)

        return processed_payload

    def run(self) -> None:
        while not self.stop_event.is_set():
            payload = self.get_from_left()
            if payload is None:
                logger.debug("No payload")
                continue

            processed_payload = self.process(payload)
            self.put_to_right(processed_payload)
