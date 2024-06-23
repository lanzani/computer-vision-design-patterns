# -*- coding: utf-8 -*-
from __future__ import annotations
from computer_vision_design_patterns.pipeline import ProcessStage1to1
import multiprocessing as mp
from computer_vision_design_patterns.pipeline import Payload


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
        pass

    def run(self) -> None:
        pass
