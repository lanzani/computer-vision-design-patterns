# -*- coding: utf-8 -*-
from __future__ import annotations
import queue
import threading
from abc import ABC

import multiprocessing as mp
from typing import Dict

from loguru import logger

from computer_vision_design_patterns.pipeline import Payload
from computer_vision_design_patterns.pipeline.stage import Stage, ThreadStage, ProcessStage


class StageNtoN(Stage, ABC):
    def __init__(
        self,
        key: str,
        output_maxsize: int | None = None,
        queue_timeout: int | None = None,
        control_queue: mp.Queue | None = None,
    ):
        self.key = key

        self.output_maxsize = output_maxsize
        self.queue_timeout = queue_timeout
        self.control_queue = control_queue

        self.input_queues: dict[str, mp.Queue[Payload]] | None = None
        self.output_queues: dict[str, mp.Queue[Payload]] | None = None

    def get_from_left(self) -> dict[str, Payload] | None:
        if self.input_queues is None:
            logger.error(f"Input queues are not set in stage '{self.key}'")
            raise ValueError("Input queue are not set in stage")

        payloads: dict[str, Payload] = {}

        for key, input_queue in list(self.input_queues.items()):
            try:
                payloads[key] = input_queue.get(timeout=self.queue_timeout)
            except queue.Empty:
                continue

        return payloads if payloads else None

    def put_to_right(self, payloads: dict[str, Payload]) -> None:
        if self.output_queues is None:
            return

        for key, output_queue in list(self.output_queues.items()):
            processed_payload = payloads.get(key)
            if processed_payload is None:
                continue

            if output_queue.full():
                logger.warning(f"Queue {key} is full, dropping frame")
                output_queue.get()

            output_queue.put(processed_payload)

    def link(self, stage: Stage) -> None:
        pass
