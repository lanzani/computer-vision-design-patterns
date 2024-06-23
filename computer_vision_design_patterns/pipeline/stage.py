# -*- coding: utf-8 -*-
from __future__ import annotations

from abc import abstractmethod, ABC
import multiprocessing as mp
import queue
import threading

from computer_vision_design_patterns.pipeline import Payload
from loguru import logger


class Stage(ABC):
    key: str
    output_maxsize: int | None
    queue_timeout: int | None
    control_queue: mp.Queue | None

    @abstractmethod
    def get_from_left(self) -> Payload | dict[str, Payload] | None:
        pass

    @abstractmethod
    def put_to_right(self, payload: Payload | dict[str, Payload]) -> None:
        pass

    @abstractmethod
    def link(self, stage: Stage) -> None:
        pass

    @abstractmethod
    def process(self, payload: Payload | None):
        pass

    @abstractmethod
    def run(self) -> None:
        pass


class ProcessStage(mp.Process):
    def __init__(self):
        super().__init__()
        self.stop_event = mp.Event()

    def terminate(self):
        self.stop_event.set()


class ThreadStage(threading.Thread):
    def __init__(self):
        super().__init__()
        self.stop_event = threading.Event()

    def terminate(self):
        self.stop_event.set()


# class ProcessStage(Stage, mp.Process):
#     def __init__(
#         self, key: str, output_maxsize: int | None, control_queue: mp.Queue | None, queue_timeout: int | None = None
#     ):
#         super().__init__()
#         self.key = key
#         self.output_maxsize = output_maxsize
#         self.input_queue: mp.Queue[Payload] | None = None
#         self.output_queue: mp.Queue[Payload] | None = None
#         self.control_queue = control_queue
#         self.queue_timeout = queue_timeout
#
#     def get_from_input_queue(self) -> Payload | None:
#         try:
#             return self.input_queue.get(timeout=self.queue_timeout)
#         except queue.Empty:
#             return None
#
#     def put_to_output_queue(self, payload: Payload) -> None:
#         if self.output_queue is None:
#             return
#
#         if self.output_queue.full():
#             logger.warning("Queue is full, dropping frame")
#             self.output_queue.get()
#         self.output_queue.put(payload)
#
#     def link(self, stage: Stage):
#         if self.output_queue is None:
#             self.output_queue = mp.Queue() if self.output_maxsize is None else mp.Queue(maxsize=self.output_maxsize)
#
#         if isinstance(stage, ProcessStage):
#             stage.input_queue = self.output_queue
#
#         elif isinstance(stage, MultiQueueThreadStage):
#             stage.input_queues[self.key] = self.output_queue
#
#     @abstractmethod
#     def process(self, payload: Payload | None):
#         pass
#
#     @abstractmethod
#     def run(self) -> None:
#         pass
#
#
# class MultiQueueThreadStage(Stage, threading.Thread):
#     def __init__(
#         self, key: str, output_maxsize: int | None, control_queue: mp.Queue | None, queue_timeout: int | None = None
#     ):
#         super().__init__()
#         self.key = key
#         self.output_maxsize = output_maxsize
#         self.input_queues: dict[str, mp.Queue[Payload]] | None = {}
#         self.output_queues: dict[str, mp.Queue[Payload]] | None = {}
#         self.control_queue = control_queue
#         self.queue_timeout = queue_timeout
#
#         self.stop_event = threading.Event()
#
#     def get_from_input_queue(self) -> dict[str, Payload]:
#         payloads: dict[str, Payload] = {}
#
#         for key, input_queue in list(self.input_queues.items()):
#             try:
#                 payloads[key] = input_queue.get(timeout=self.queue_timeout)
#             except queue.Empty:
#                 continue
#
#         return payloads
#
#     def put_to_output_queue(self, processed_payloads: dict[str, Payload]) -> None:
#         for key, output_queue in list(self.output_queues.items()):
#             processed_payload = processed_payloads.get(key)
#             if processed_payload is None:
#                 continue
#
#             # If the queue exists and is full
#             if output_queue.full():
#                 logger.warning("Queue is full, dropping payload")
#                 output_queue.get()  # Remove an item from the queue to make space
#
#             output_queue.put(processed_payload)
#
#     def close_queue(self, key: str):
#         del self.input_queues[key]
#         del self.output_queues[key]
#
#     def link(self, stage: ProcessStage | MultiQueueThreadStage):
#         if isinstance(stage, ProcessStage):
#             if self.output_queues.get(stage.key) is None:
#                 self.output_queues[stage.key] = (
#                     mp.Queue() if self.output_maxsize is None else mp.Queue(maxsize=self.output_maxsize)
#                 )
#
#             stage.input_queue = self.output_queues[stage.key]
#
#         elif isinstance(stage, MultiQueueThreadStage):
#             stage_keys = list(stage.output_queues.keys())
#
#             for key in stage_keys:
#                 if self.output_queues.get(key) is None:
#                     self.output_queues[key] = (
#                         mp.Queue() if self.output_maxsize is None else mp.Queue(maxsize=self.output_maxsize)
#                     )
#
#                 stage.input_queues[self.key] = self.output_queues[key]
#
#     def terminate(self):
#         self.stop_event.set()
#
#     @abstractmethod
#     def process(self, key, payload: Payload):
#         pass
#
#     @abstractmethod
#     def run(self) -> None:
#         pass
