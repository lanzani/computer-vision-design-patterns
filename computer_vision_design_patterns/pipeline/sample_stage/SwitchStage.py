# -*- coding: utf-8 -*-
from __future__ import annotations
from computer_vision_design_patterns.pipeline import ProcessStage, Stage1toN, Payload
import multiprocessing as mp
from loguru import logger

executor = ProcessStage


class SwitchStage(Stage1toN, executor):
    def __init__(
        self,
        key: str,
        output_maxsize: int | None = None,
        queue_timeout: int | None = None,
        control_queue: mp.Queue | None = None,
    ):
        Stage1toN.__init__(self, key, output_maxsize, queue_timeout, control_queue)
        executor.__init__(self, name=f"SwitchStage {key}")

    def process(self, payload: Payload):
        processed_payloads = {key: payload for key in list(self.output_queues.keys())}

        return processed_payloads

    def run(self) -> None:
        while not self.stop_event.is_set():
            payload = self.get_from_left()
            if payload is None:
                logger.debug("No payload")
                continue

            processed_payloads = self.process(payload)
            self.put_to_right(processed_payloads)
