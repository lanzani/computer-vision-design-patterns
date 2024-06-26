# -*- coding: utf-8 -*-
from __future__ import annotations

import cv2

from computer_vision_design_patterns.pipeline import ProcessStage, StageNtoN, Payload
import multiprocessing as mp
from loguru import logger

from computer_vision_design_patterns.pipeline.sample_stage.SimpleStreamStage import VideoStreamOutput

executor = ProcessStage


class RGB2GRAYStage(StageNtoN, executor):
    def __init__(
        self,
        key: str,
        output_maxsize: int | None = None,
        queue_timeout: int | None = None,
        control_queue: mp.Queue | None = None,
    ):
        StageNtoN.__init__(self, key, output_maxsize, queue_timeout, control_queue)
        executor.__init__(self, name=f"RGB2GRAYStage {key}")

    def process(self, payload: dict[str, Payload]):
        processed_payloads = {}

        for key, value in payload.items():
            frame = value.frame
            if frame is None:
                continue

            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            processed_payloads[key] = VideoStreamOutput(timestamp=value.timestamp, frame=gray)

        return processed_payloads

    def run(self) -> None:
        while not self.stop_event.is_set():
            payload = self.get_from_left()
            if payload is None:
                logger.warning("No payload")
                continue

            processed_payloads = self.process(payload)
            self.put_to_right(processed_payloads)
