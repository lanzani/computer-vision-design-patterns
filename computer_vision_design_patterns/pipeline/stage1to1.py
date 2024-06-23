# -*- coding: utf-8 -*-
from __future__ import annotations
import queue
import threading
from abc import ABC

import multiprocessing as mp
from loguru import logger

from computer_vision_design_patterns.pipeline import Payload
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

        self.input_queue: mp.Queue[Payload] | None = None
        self.output_queue: mp.Queue[Payload] | None = None

    def get_from_left(self) -> Payload | None:
        if self.input_queue is None:
            logger.error(f"Input queue is not set in stage '{self.key}'")
            return None

        try:
            return self.input_queue.get(timeout=self.queue_timeout)
        except queue.Empty:
            return None

    def put_to_right(self, payload: Payload) -> None:
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
        if isinstance(stage, self.__class__):
            stage.input_queue = self.output_queue


class ProcessStage1to1(Stage1to1, mp.Process, ABC):
    def __init__(
        self,
        key: str,
        output_maxsize: int | None = None,
        queue_timeout: int | None = None,
        control_queue: mp.Queue | None = None,
    ):
        Stage1to1.__init__(self, key, output_maxsize, queue_timeout, control_queue)
        mp.Process.__init__(self)


class ThreadStage1to1(Stage1to1, threading.Thread, ABC):
    def __init__(
        self,
        key: str,
        output_maxsize: int | None = None,
        queue_timeout: int | None = None,
        control_queue: mp.Queue | None = None,
    ):
        Stage1to1.__init__(self, key, output_maxsize, queue_timeout, control_queue)
        threading.Thread.__init__(self)