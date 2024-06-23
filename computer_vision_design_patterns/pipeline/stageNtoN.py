# -*- coding: utf-8 -*-
from __future__ import annotations
import queue
import threading
from abc import ABC

import multiprocessing as mp
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

        self.input_queue: mp.Queue[Payload] | None = None
        self.output_queue: mp.Queue[Payload] | None = None

    def get_from_left(self) -> Payload | None:
        pass

    def put_to_right(self, payload: Payload) -> None:
        pass

    def link(self, stage: Stage) -> None:
        pass


# class ProcessStageNtoN(StageNtoN, ProcessStage, ABC):
#     def __init__(
#             self,
#             key: str,
#             output_maxsize: int | None = None,
#             queue_timeout: int | None = None,
#             control_queue: mp.Queue | None = None,
#     ):
#         StageNtoN.__init__(self, key, output_maxsize, queue_timeout, control_queue)
#         mp.Process.__init__(self)
#
#
# class ThreadStageNtoN(StageNtoN, ThreadStage, ABC):
#     def __init__(
#             self,
#             key: str,
#             output_maxsize: int | None = None,
#             queue_timeout: int | None = None,
#             control_queue: mp.Queue | None = None,
#     ):
#         StageNtoN.__init__(self, key, output_maxsize, queue_timeout, control_queue)
#         threading.Thread.__init__(self)
