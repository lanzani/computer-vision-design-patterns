# -*- coding: utf-8 -*-
from __future__ import annotations
import queue

from abc import ABC

import multiprocessing as mp
from loguru import logger

from computer_vision_design_patterns import pipeline as pipe
from computer_vision_design_patterns.pipeline.stage import Stage


class Stage1to1(Stage, ABC):
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

        self.input_queue: mp.Queue[pipe.Payload] | None = None
        self.output_queue: mp.Queue[pipe.Payload] | None = None

    def get_from_left(self) -> pipe.Payload | None:
        if self.input_queue is None:
            logger.error(f"Input queue is not set in stage '{self.key}'")
            raise ValueError("Input queue is not set in stage")

        try:
            return self.input_queue.get(timeout=self.queue_timeout)
        except queue.Empty:
            return None

    def put_to_right(self, payload: pipe.Payload) -> None:
        if self.output_queue is None:
            return

        if self.output_queue.full():
            logger.warning("Queue is full, dropping frame")
            self.output_queue.get()
        self.output_queue.put(payload)

    def link(self, stage: Stage) -> None:
        # Create output queue
        if self.output_queue is None:
            self.output_queue = mp.Queue() if self.output_maxsize is None else mp.Queue(maxsize=self.output_maxsize)

        # Link output queue of this stage to input queue of the next stage
        if isinstance(stage, Stage1to1):
            stage.input_queue = self.output_queue

        elif isinstance(stage, pipe.StageNtoN):
            if stage.input_queues is None:
                stage.input_queues = {}
            stage.input_queues[self.key] = self.output_queue

        else:
            raise TypeError("Link not supported.")
