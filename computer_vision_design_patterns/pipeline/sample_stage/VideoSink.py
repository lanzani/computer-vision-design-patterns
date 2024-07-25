# -*- coding: utf-8 -*-
from __future__ import annotations

import cv2

from computer_vision_design_patterns.pipeline import Payload

from computer_vision_design_patterns.pipeline.stage import StageExecutor, Stage, StageType


class VideoSink(Stage):
    def __init__(self, stage_executor: StageExecutor):
        Stage.__init__(self, stage_type=StageType.One2One, stage_executor=stage_executor)

    def pre_run(self):
        pass

    def post_run(self):
        cv2.destroyAllWindows()

    def process(self, data: dict[str, Payload]) -> dict[str, Payload]:
        for key, payload in data.items():
            frame = payload.frame
            if frame is None:
                return {}

            cv2.imshow(f"VideoSink {key}", frame)
            user_input = cv2.waitKey(1) & 0xFF

            if user_input == ord("q"):
                cv2.destroyAllWindows()
                exit(0)

        return {}
