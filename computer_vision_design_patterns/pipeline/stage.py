# -*- coding: utf-8 -*-
from __future__ import annotations

import time
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


class PoisonPill(Payload):
    pass


class QueuePoisonPill:
    pass


class Stage(ABC):
    def __init__(
        self,
        stage_type: StageType,
        stage_executor: StageExecutor,
        output_maxsize: int | None = None,
        queue_timeout: float = 0.1,
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

        # Create snapshot to avoid "dictionary changed size during iteration" error
        input_queues = self.input_queues.copy()

        for key, queue in input_queues.items():
            try:
                data = queue.get(timeout=self._queue_timeout)

            except (ValueError, OSError):
                logger.error(f"Queue {key} is closed")
                continue

            except Empty:
                continue

            if isinstance(data, PoisonPill):
                self.poison_pill()
                return {}

            result[key] = data

        return result if result else {}

    def put_to_right(self, payloads: dict[str, Payload]) -> None:
        """Put data to the next stage / stages."""
        if not self._output_queues:
            return None

        # Create snapshot to avoid "dictionary changed size during iteration" error
        output_queues = self._output_queues.copy()

        for key, output_queue in output_queues.items():
            processed_payload = payloads.get(key)
            if processed_payload is None:
                continue

            try:
                output_queue.put(processed_payload, timeout=self._queue_timeout)

            except (ValueError, OSError):
                logger.error(f"Queue {key} is closed")
                continue

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

            except KeyboardInterrupt:
                logger.error(f"Keyboard interrupt in {self.__class__.__name__}")
                self.stop()

            except Exception as e:
                logger.exception(e)
                logger.error(f"Error in {self.__class__.__name__}: {str(e)}")
                # TODO add crash callback

        self.post_run()

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

    def unlink(self, stream_id: str) -> None:
        for key in list(self.input_queues.keys()):
            if stream_id in key:
                del self.input_queues[key]

        for key in list(self._output_queues.keys()):
            if stream_id in key:
                del self._output_queues[key]

        if len(self.input_queues) == 0 and len(self._output_queues) == 0:
            self.stop()
            self.join()

    def start(self):
        self._running.set()
        self._worker.start()

    def stop(self):
        logger.info(f"Stopping {self.__class__.__name__}")
        self._running.clear()
        time.sleep(0.1)

    def join(self):
        if self._worker:
            self._worker.join(timeout=self._queue_timeout * 2)

            if self._worker.is_alive():
                logger.warning(f"Worker in {self.__class__.__name__} did not stop gracefully")
                if self._stage_executor == StageExecutor.PROCESS:
                    self._worker.terminate()
                self._worker.join(timeout=self._queue_timeout * 2)

                if self._worker.is_alive():
                    logger.error(f"Worker in {self.__class__.__name__} is still alive, will be killed")
                    if self._stage_executor == StageExecutor.PROCESS:
                        self._worker.kill()

            logger.info(f"Stopped {self.__class__.__name__}")

    def poison_pill(self):
        """Poison the stage and the stages linked in output."""
        self.stop()
        self.put_to_right({key: PoisonPill() for key in self._output_queues.keys()})

    # def queue_poison_pill(self, key: str):
    #     """Poison a specific queue."""
    #     if key in self._output_queues:
    #         self._output_queues[key].put(QueuePoisonPill())
    #     else:
    #         logger.warning(f"Queue {key} not found")
    #
    #     self._running.clear()
