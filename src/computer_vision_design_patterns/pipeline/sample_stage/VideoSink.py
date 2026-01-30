# -*- coding: utf-8 -*-
from __future__ import annotations

import cv2

from computer_vision_design_patterns.pipeline import Payload
from computer_vision_design_patterns.pipeline.stage import Stage, StageType


class VideoSink(Stage):
    def __init__(self, stage_executor, daemon: bool | None = None, input_queues_timeout: float | None = 0.1):
        Stage.__init__(
            self,
            stage_type=StageType.ONE_TO_ONE,
            stage_executor=stage_executor,
            daemon=daemon,
            input_queues_timeout=input_queues_timeout,
        )

    def pre_run(self):
        pass

    def post_run(self):
        pass

    def process(self, key: str, payload: Payload | None) -> Payload | None:
        if payload is None:
            return None

        if not hasattr(payload, "frame"):
            return None

        frame = payload.frame
        if frame is None:
            return None

        cv2.imshow(f"VideoSink {key}", frame)
        user_input = cv2.waitKey(1) & 0xFF

        if user_input == ord("q"):
            self._running.clear()
            cv2.destroyAllWindows()
            return None

        return payload
