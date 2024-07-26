# -*- coding: utf-8 -*-
from __future__ import annotations

from abc import abstractmethod, ABC
import multiprocessing as mp
from enum import Enum
from queue import Empty, Full
import threading

from computer_vision_design_patterns.pipeline import Payload
from loguru import logger


class StageExecutor(Enum):
    THREAD = 1
    PROCESS = 2


class StageType(Enum):
    One2One = 1
    One2Many = 2
    Many2One = 3
    Many2Many = 4


class PoisonPill:
    pass


class Stage(ABC):
    def __init__(
        self,
        stage_type: StageType,
        stage_executor: StageExecutor,
        output_maxsize: int | None = None,
        queue_timeout: int = 0.1,
    ):
        self._output_maxsize = output_maxsize
        self._queue_timeout = queue_timeout

        self.input_queues: dict[str, mp.Queue] = {}
        self._output_queues: dict[str, mp.Queue] = {}

        self._stage_type: StageType = stage_type
        self._stage_executor: StageExecutor = stage_executor

        if self._stage_executor == StageExecutor.THREAD:
            self._running = threading.Event()
            self._worker = threading.Thread(target=self._run)

        elif self._stage_executor == StageExecutor.PROCESS:
            self._running = mp.Event()
            self._worker = mp.Process(target=self._run)

        else:
            raise ValueError(f"Invalid stage executor: {self._stage_executor}")

    @abstractmethod
    def pre_run(self):
        pass

    @abstractmethod
    def post_run(self):
        pass

    @abstractmethod
    def process(self, data: dict[str, Payload]) -> dict[str, Payload]:
        pass

    def is_alive(self) -> bool:
        return self._worker.is_alive()

    def get_from_left(self) -> dict[str, Payload]:
        """Get data from the previous stage / stages."""
        if not self.input_queues:
            return {}

        result: dict[str, Payload] = {}
        for key, queue in self.input_queues.items():
            try:
                data = queue.get(timeout=self._queue_timeout)
            except Empty:
                continue

            if isinstance(data, PoisonPill):
                self._running.clear()
                return {}

            result[key] = data

        return result if result else {}

    def put_to_right(self, payloads: dict[str, Payload]) -> None:
        """Put data to the next stage / stages."""
        if not self._output_queues:
            return None

        for key, output_queue in self._output_queues.items():
            processed_payload = payloads.get(key)
            if processed_payload is None:
                continue

            try:
                output_queue.put(processed_payload, timeout=self._queue_timeout)
            except Full:
                logger.warning(f"Queue {key} is full, dropping frame")
                try:
                    output_queue.get_nowait()
                    output_queue.put_nowait(processed_payload)
                except (Empty, Full):
                    pass

    def _run(self):
        logger.info(f"Starting {self.__class__.__name__}")
        self.pre_run()
        logger.info(f"Running {self.__class__.__name__}")

        while self._running.is_set():
            try:
                input_data = self.get_from_left()
                output_data = self.process(input_data)
                self.put_to_right(output_data)
            except Exception as e:
                logger.error(f"Error in {self.__class__.__name__}: {str(e)}")
                # raise e
                # TODO add crash callback

            except KeyboardInterrupt:
                logger.error(f"Keyboard interrupt in {self.__class__.__name__}")
                self._running.clear()

        logger.info(f"Stopping {self.__class__.__name__}")
        self.post_run()
        logger.info(f"Stopped {self.__class__.__name__}")
        exit(0)

    def link(self, stage: Stage, key: str) -> None:
        # Check if the stage can be linked based on the stage type
        if self._stage_type in [StageType.One2One, StageType.Many2One] and len(self._output_queues) > 0:
            raise ValueError(f"Cannot link more outputs for stage type {self._stage_type}")

        if stage._stage_type in [StageType.One2One, StageType.One2Many] and len(stage.input_queues) > 0:
            raise ValueError(f"Cannot link more inputs for stage type {stage._stage_type}")

        maxsize = self._output_maxsize if self._output_maxsize is not None else 0

        # manager = multiprocessing.Manager()
        queue: mp.Queue = mp.Queue(maxsize=maxsize)

        self._output_queues[key] = queue
        stage.input_queues[key] = queue

    def unlink(self, key: str) -> None:
        if key in self._output_queues:
            del self._output_queues[key]

        if key in self.input_queues:
            del self.input_queues[key]

        if not self.input_queues:
            self.stop()

    def start(self):
        self._running.set()
        self._worker.start()

    def stop(self):
        self._running.clear()

        if self._worker:
            self._worker.join(timeout=5)
            if self._worker.is_alive():
                logger.warning(f"Worker in {self.__class__.__name__} did not stop gracefully")
                self._worker.terminate()

    def poison_pill(self):
        for queue in self._output_queues.values():
            queue.put(PoisonPill())

        self._running.clear()
