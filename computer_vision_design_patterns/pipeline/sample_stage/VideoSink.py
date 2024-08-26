# -*- coding: utf-8 -*-
from __future__ import annotations

import time

import cv2

from computer_vision_design_patterns.pipeline import Payload
from computer_vision_design_patterns.pipeline.stage import Stage, StageType
from loguru import logger


class VideoSink(Stage):
    def __init__(self, stage_executor):
        Stage.__init__(self, stage_type=StageType.One2One, stage_executor=stage_executor)
        self.window_name = None

    def pre_run(self):
        self.window_name = f"VideoSink {id(self)}"
        cv2.namedWindow(self.window_name)

    def post_run(self):
        logger.info(f"Closing window {self.window_name}")
        cv2.destroyWindow(self.window_name)

    def process(self, key: str, payload: Payload | None) -> Payload | None:
        if self._stop_flag.is_set():
            logger.info(f"Stop flag set for {self.__class__.__name__}, stopping")
            return None

        if payload is None:
            return None

        frame = payload.frame
        if frame is None:
            return None

        cv2.imshow(self.window_name, frame)
        self.check_for_key_press()

        return payload

    def check_for_key_press(self):
        for _ in range(10):  # Check multiple times to be more responsive
            if self._stop_flag.is_set():
                return

            key = cv2.waitKey(1) & 0xFF
            if key == ord("q"):
                logger.info(f"'q' key pressed in {self.__class__.__name__}, stopping")
                self._running.clear()
                self.set_stop_flag()
                return

            time.sleep(0.01)  # Short sleep to prevent busy-waiting
