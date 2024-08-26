# -*- coding: utf-8 -*-
from abc import abstractmethod, ABC
import multiprocessing as mp
import threading
from enum import Enum
from queue import Empty, Full
import ctypes
import time

from loguru import logger


class StageExecutor(Enum):
    THREAD = 1
    PROCESS = 2


class StageType(Enum):
    One2One = 1
    One2Many = 2
    Many2One = 3
    Many2Many = 4


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
            self._stop_flag = threading.Event()

        elif self._stage_executor == StageExecutor.PROCESS:
            self._running = mp.Event()
            self._worker = mp.Process(target=self._run)
            self._stop_flag = mp.Event()

        else:
            raise ValueError(f"Invalid stage executor: {self._stage_executor}")

    @abstractmethod
    def pre_run(self):
        pass

    @abstractmethod
    def post_run(self):
        pass

    @abstractmethod
    def process(self, key: str, payload):
        pass

    def is_alive(self) -> bool:
        return self._worker.is_alive()

    def set_stop_flag(self):
        logger.info(f"Setting stop flag for {self.__class__.__name__}")
        self._stop_flag.set()

    def force_stop(self):
        logger.warning(f"Force stopping {self.__class__.__name__}")
        if self._stage_executor == StageExecutor.THREAD:
            if self._worker.is_alive():
                ctypes.pythonapi.PyThreadState_SetAsyncExc(
                    ctypes.c_long(self._worker.ident), ctypes.py_object(SystemExit)
                )
        elif self._stage_executor == StageExecutor.PROCESS:
            if self._worker.is_alive():
                self._worker.terminate()

    def get_from_left(self, key: str):
        queue = self.input_queues.get(key)
        if queue is None:
            return None

        try:
            data = queue.get(timeout=self._queue_timeout)
        except Empty:
            return None
        except (ValueError, OSError):
            logger.error(f"Queue {key} is closed")
            return None

        return data if data else None

    def put_to_right(self, key: str, payload: any) -> None:
        queue = self._output_queues.get(key)
        if queue is None:
            return None

        try:
            queue.put(payload, timeout=self._queue_timeout)
        except Full:
            logger.warning(f"Queue {key} is full, dropping frame")
            try:
                queue.get_nowait()
                queue.put_nowait(payload)
            except (Empty, Full):
                pass
        except (ValueError, OSError):
            logger.error(f"Queue {key} is closed")
            return None

    def _process_stage(self):
        if self._stop_flag.is_set():
            logger.info(f"{self.__class__.__name__} received stop signal, stopping")
            self._running.clear()
            return

        input_keys = set(self.input_queues.keys())
        output_keys = set(self._output_queues.keys())

        keys_to_process = input_keys if input_keys else output_keys

        for key in keys_to_process:
            payload = self.get_from_left(key) if input_keys else None

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

        while self._running.is_set() and not self._stop_flag.is_set():
            try:
                self._process_stage()
            except Exception as e:
                logger.exception(e)
                logger.error(f"Error in {self.__class__.__name__}: {str(e)}")

        logger.info(f"{self.__class__.__name__} is stopping")
        self.post_run()
        logger.info(f"{self.__class__.__name__} has stopped")

    def link(self, stage, key: str, queue: mp.Queue) -> None:
        if self._stage_type in [StageType.One2One, StageType.Many2One] and len(self._output_queues) > 0:
            raise ValueError(f"Cannot link more outputs for stage type {self._stage_type}")

        if stage._stage_type in [StageType.One2One, StageType.One2Many] and len(stage.input_queues) > 0:
            raise ValueError(f"Cannot link more inputs for stage type {stage._stage_type}")

        self._output_queues[key] = queue
        stage.input_queues[key] = queue

    def start(self):
        self._running.set()
        self._worker.start()

    def stop(self):
        logger.info(f"Stopping {self.__class__.__name__}")
        self.set_stop_flag()
        self._running.clear()

    def join(self):
        if self._worker:
            self._worker.join(timeout=self._queue_timeout * 2)

            if self._worker.is_alive():
                logger.warning(f"Worker in {self.__class__.__name__} did not stop gracefully")
                self.force_stop()
                self._worker.join(timeout=self._queue_timeout * 2)

                if self._worker.is_alive():
                    logger.error(f"Worker in {self.__class__.__name__} is still alive after force stop")

            logger.info(f"Stopped {self.__class__.__name__}")
