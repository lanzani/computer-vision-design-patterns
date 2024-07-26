# -*- coding: utf-8 -*-
from __future__ import annotations
from computer_vision_design_patterns.pipeline import Payload, Stage
import multiprocessing as mp

from computer_vision_design_patterns.pipeline.stage import StageExecutor, StageType


class SwitchStage(Stage):
    def __init__(
        self, stage_executor: StageExecutor, output_maxsize: int | None = None, queue_timeout: int | None = None
    ):
        Stage.__init__(
            self,
            stage_type=StageType.One2Many,
            stage_executor=stage_executor,
            output_maxsize=output_maxsize,
            queue_timeout=queue_timeout,
        )

    def pre_run(self):
        pass

    def post_run(self):
        pass

    def process(self, data: dict[str, Payload]) -> dict[str, Payload]:
        processed_payload = {}

        for _, payload in data.items():
            processed_payload = {key: payload for key in self._output_queues.keys()}

        return processed_payload

    def link(self, stage: Stage, key: str) -> None:
        copy_key = f"{key}-{len(list(self._output_queues.keys()))}"

        maxsize = self._output_maxsize if self._output_maxsize is not None else 0

        queue: mp.Queue = mp.Queue(maxsize=maxsize)

        self._output_queues[copy_key] = queue
        stage.input_queues[key] = queue
