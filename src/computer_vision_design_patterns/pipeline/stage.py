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
    def process(self, key: str, payload: Payload | None) -> Payload | None:
        if isinstance(payload, PoisonPill):
            self._running.clear()
            return None

    def is_alive(self) -> bool:
        return self._worker.is_alive()

    def get_from_left(self, key: str) -> Payload | None:
        """Get data from the previous stage / stages."""
        queue = self.input_queues.get(key)
        if queue is None:
            return None

        try:
            data = queue.get(timeout=self._queue_timeout)

        except (ValueError, OSError):
            logger.error(f"Queue {key} is closed")
            return None

        except Empty:
            return None

        return data if data else None

    def put_to_right(self, key: str, payload: Payload) -> None:
        """Put data to the next stage / stages."""
        queue = self._output_queues.get(key)
        if queue is None:
            return None

        try:
            queue.put(payload, timeout=self._queue_timeout)

        except (ValueError, OSError):
            logger.error(f"Queue {key} is closed")
            return None

        except Full:
            logger.warning(f"Queue {self.__class__.__name__}, Output queue {key} is full, dropping frame")
            try:
                queue.get_nowait()
                queue.put_nowait(payload)
            except (Empty, Full):
                pass

    def _process_stage(self):
        input_keys = set(self.input_queues.keys())
        output_keys = set(self._output_queues.keys())

        keys_to_process = input_keys if input_keys else output_keys

        for key in keys_to_process:
            payload = self.get_from_left(key)
            if isinstance(payload, PoisonPill):
                self._running.clear()
                break
            processed_payload = self.process(key, payload)

            if processed_payload is None or not output_keys:
                continue

            if self._stage_type == StageType.One2Many:
                for output_key in output_keys:
                    self.put_to_right(output_key, processed_payload)
            else:
                self.put_to_right(key, processed_payload)

    def _run(self):
        logger.info(f"Starting {self.__class__.__name__}")
        self.pre_run()
        logger.info(f"Running {self.__class__.__name__}")

        while self._running.is_set():
            try:
                self._process_stage()

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

        queue: mp.Queue = mp.Queue(maxsize=maxsize)

        self._output_queues[key] = queue
        stage.input_queues[key] = queue

    def unlink(self, stream_id: str) -> None:
        for key in set(self.input_queues.keys()):
            if stream_id in key:
                self.input_queues[key].close()
                self.input_queues[key].join_thread()
                del self.input_queues[key]

        for key in set(self._output_queues.keys()):
            if stream_id in key:
                self._output_queues[key].close()
                self._output_queues[key].join_thread()
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

    # def poison_pill(self):
    #     """Poison the stage and the stages linked in output."""
    #     self.put_to_right({key: PoisonPill() for key in self._output_queues.keys()})
    #     self.stop()

    # def queue_poison_pill(self, key: str):
    #     """Poison a specific queue."""
    #     if key in self._output_queues:
    #         self._output_queues[key].put(QueuePoisonPill())
    #     else:
    #         logger.warning(f"Queue {key} not found")
    #
    #     self._running.clear()
