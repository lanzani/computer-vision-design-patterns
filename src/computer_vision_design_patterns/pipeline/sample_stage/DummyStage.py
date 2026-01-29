# -*- coding: utf-8 -*-
from __future__ import annotations

from computer_vision_design_patterns.pipeline import ProcessStage, StageNtoN, Payload, Stage1to1
import multiprocessing as mp

executor = ProcessStage


class DummyStage1to1(Stage1to1, executor):
    def __init__(
        self,
        key: str,
        output_maxsize: int | None = None,
        queue_timeout: int | None = None,
        control_queue: mp.Queue | None = None,
    ):
        Stage1to1.__init__(self, key, output_maxsize, queue_timeout, control_queue)
        executor.__init__(self)

    def process(self, payload: Payload | None):
        pass

    def run(self) -> None:
        pass


class DummyStageNtoN(StageNtoN, executor):
    def __init__(
        self,
        key: str,
        output_maxsize: int | None = None,
        queue_timeout: int | None = None,
        control_queue: mp.Queue | None = None,
    ):
        StageNtoN.__init__(self, key, output_maxsize, queue_timeout, control_queue)
        executor.__init__(self)

    def process(self, payload: Payload | None):
        pass

    def run(self) -> None:
        pass
