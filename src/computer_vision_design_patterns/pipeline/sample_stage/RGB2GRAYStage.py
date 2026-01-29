# -*- coding: utf-8 -*-
from __future__ import annotations


import cv2

from computer_vision_design_patterns.pipeline import Payload, Stage


from computer_vision_design_patterns.pipeline.sample_stage.SimpleStreamStage import VideoStreamOutput
from computer_vision_design_patterns.pipeline.stage import StageExecutor, StageType


class RGB2GRAYStage(Stage):
    def __init__(self, stage_executor: StageExecutor):
        Stage.__init__(self, stage_type=StageType.Many2Many, stage_executor=stage_executor)

    def pre_run(self):
        pass

    def post_run(self):
        pass

    def process(self, key: str, payload: Payload | None) -> Payload | None:
        if payload is None:
            return None

        frame = payload.frame
        if frame is None:
            return None

        # time.sleep(0.06)
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        return VideoStreamOutput(timestamp=payload.timestamp, frame=gray)
