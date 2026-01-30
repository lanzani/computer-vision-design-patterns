# -*- coding: utf-8 -*-
from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np

from computer_vision_design_patterns.pipeline import Payload
from computer_vision_design_patterns.pipeline.stage import Stage, StageExecutor, StageType


@dataclass(frozen=True, eq=False, slots=True, kw_only=True)
class VideoStreamOutput(Payload):
    frame: np.ndarray | None


class SimpleStreamStage(Stage):
    def __init__(
        self,
        source: int,
        stage_executor: StageExecutor,
        daemon: bool | None = None,
        output_queues_maxsize: int | None = None,
        input_queues_timeout: float | None = 0.1,
        output_queues_timeout: float | None = 0.1,
    ):
        Stage.__init__(
            self,
            stage_type=StageType.ONE_TO_ONE,
            stage_executor=stage_executor,
            daemon=daemon,
            output_queues_maxsize=output_queues_maxsize,
            input_queues_timeout=input_queues_timeout,
            output_queues_timeout=output_queues_timeout,
        )

        self.source = source
        self._cap = None

    def pre_run(self):
        self._cap = cv2.VideoCapture(self.source)

    def post_run(self):
        if self._cap is not None:
            self._cap.release()
            self._cap = None

    def process(self, key: str, payload: Payload | None) -> Payload | None:
        if self._cap is None:
            return None

        ret, frame = self._cap.read()
        if not ret:
            return None

        return VideoStreamOutput(frame=frame)
