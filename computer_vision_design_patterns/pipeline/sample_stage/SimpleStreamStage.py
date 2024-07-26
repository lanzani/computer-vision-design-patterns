# -*- coding: utf-8 -*-
from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np

from computer_vision_design_patterns.pipeline import Payload

from computer_vision_design_patterns.pipeline.stage import Stage, StageType, StageExecutor


@dataclass(frozen=True, eq=False, slots=True, kw_only=True)
class VideoStreamOutput(Payload):
    frame: np.ndarray | None


class SimpleStreamStage(Stage):
    def __init__(
        self,
        source: int,
        stage_executor: StageExecutor,
        output_maxsize: int | None = None,
        queue_timeout: int | None = None,
    ):
        Stage.__init__(
            self,
            stage_type=StageType.One2One,
            stage_executor=stage_executor,
            output_maxsize=output_maxsize,
            queue_timeout=queue_timeout,
        )

        self.source = source
        self._cap = None

    def pre_run(self):
        self._cap = cv2.VideoCapture(self.source)

    def post_run(self):
        self._cap.release()

    def process(self, data: dict[str, Payload]) -> dict[str, Payload]:
        ret, frame = self._cap.read()
        if not ret:
            return {}

        return {key: VideoStreamOutput(frame=frame) for key in self._output_queues.keys()}
