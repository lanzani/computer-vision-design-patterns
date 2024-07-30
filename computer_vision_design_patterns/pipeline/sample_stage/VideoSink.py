# -*- coding: utf-8 -*-
from __future__ import annotations

import cv2

from computer_vision_design_patterns.pipeline import Payload
from computer_vision_design_patterns.pipeline.stage import Stage, StageType, PoisonPill


class VideoSink(Stage):
    def __init__(self, stage_executor):
        Stage.__init__(self, stage_type=StageType.One2One, stage_executor=stage_executor)

    def pre_run(self):
        pass

    def post_run(self):
        cv2.destroyAllWindows()

    def process(self, key: str, payload: Payload | None) -> Payload | None:
        if isinstance(payload, PoisonPill):
            self._running.clear()
            cv2.destroyAllWindows()
            return None

        if payload is None:
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
