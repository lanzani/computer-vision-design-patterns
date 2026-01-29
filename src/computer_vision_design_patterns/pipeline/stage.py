# -*- coding: utf-8 -*-
from __future__ import annotations

import multiprocessing as mp
import threading
import time
from abc import ABC, abstractmethod
from enum import Enum
from queue import Empty, Full

from loguru import logger

from computer_vision_design_patterns.pipeline import Payload


class StageExecutor(Enum):
    """
    Execution model for pipeline stages.

    - THREAD: Stage runs in a separate thread within the same process.
              Use for I/O-bound operations or when shared memory access is needed.
              Faster startup, but subject to Python's GIL limitations for CPU-bound tasks.

    - PROCESS: Stage runs in a separate process with its own memory space.
               Use for CPU-intensive operations that benefit from true parallelism.
               Higher overhead but can utilize multiple CPU cores effectively.
    """

    THREAD = 1
    PROCESS = 2


class StageType(Enum):
    """
    Defines the input/output topology of a stage.

    The stage type determines how payloads flow through the stage:

    - One2One: Single input queue → single output queue.
               Each input payload produces exactly one output payload.
               Example: Image filter, color conversion.

    - One2Many: Single input queue → multiple output queues.
                Each input payload is broadcast to all output queues.
                Example: Duplicating a stream to multiple sinks.

    - Many2One: Multiple input queues → single output queue.
                Payloads from any input queue are processed and sent to one output.
                Example: Merging multiple video streams.

    - Many2Many: Multiple input queues → multiple output queues.
                 Payloads from any input can be routed to any output.
                 Example: Complex routing/switching logic.
    """

    One2One = 1
    One2Many = 2
    Many2One = 3
    Many2Many = 4


class Stage(ABC):
    """
    Abstract base class for pipeline computation stages.

    A Stage represents a single processing unit in the pipeline. It receives payloads
    from upstream stages, processes them, and sends results to downstream stages.

    Args:
        stage_type: The input/output topology of this stage.
        stage_executor: Whether to run in a thread or separate process.
        output_maxsize: Maximum size for output queues (0 = unlimited).
                       When full, oldest items are dropped (backpressure handling).
        queue_timeout: Timeout in seconds for queue operations (get/put).

    Example:
        Create a simple image processing stage:

        ```python
        class GrayscaleStage(Stage):
            def __init__(self, stage_executor: StageExecutor):
                super().__init__(
                    stage_type=StageType.One2One,
                    stage_executor=stage_executor
                )

            def pre_run(self):
                # Initialize resources (e.g., models, connections)
                pass

            def process(self, key: str, payload: Payload | None) -> Payload | None:
                if payload is None:
                    return None
                # Process payload and return new payload
                gray_frame = cv2.cvtColor(payload.frame, cv2.COLOR_BGR2GRAY)
                return ImagePayload(frame=gray_frame, timestamp=payload.timestamp)

            def post_run(self):
                # Cleanup resources
                pass
        ```
    """

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
        """
        Called once before the processing loop starts.

        This runs in the worker thread/process.
        """
        pass

    @abstractmethod
    def post_run(self):
        """
        Called once after the processing loop stops.

        This runs in the worker thread/process.
        """
        pass

    @abstractmethod
    def process(self, key: str, payload: Payload | None) -> Payload | None:
        """
        Process a single payload from an input queue.

        This is the core computation method called repeatedly during the processing loop.
        It receives payloads from upstream stages and returns processed payloads for
        downstream stages.

        Args:
            key: The stream identifier for the input queue that provided this payload.
                 Useful for multi-stream stages that need to distinguish between sources.
            payload: The payload to process, or None if the queue was empty.

        Returns:
            A new Payload instance with processed data, or None to skip output.
            Returning None prevents sending data downstream for this iteration.

        """
        pass

    def is_alive(self) -> bool:
        """
        Check if the stage is still running.

        Returns:
            True if the stage is running, False otherwise.
        """
        return self._worker.is_alive()

    def _get_from_left(self, key: str) -> Payload | None:
        """
        Retrieve a payload from an upstream stage's output queue.

        Args:
            key: The stream identifier for the input queue to read from.

        Returns:
            The payload if available, None if the queue is empty or closed.
            Returns None on timeout (non-blocking behavior for real-time processing).

        """
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

    def _put_to_right(self, key: str, payload: Payload) -> None:
        """
        Send a payload to a downstream stage's input queue.

        Args:
            key: The stream identifier for the output queue to write to.
            payload: The payload to send downstream.

        Note:
            - If the queue is full, the oldest item is dropped and the new payload
              is added (backpressure handling for real-time systems).
            - Returns None if the queue is closed or operation fails.
        """
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
            payload = self._get_from_left(key)
            processed_payload = self.process(key, payload)

            if processed_payload is None or not output_keys:
                continue

            if self._stage_type == StageType.One2Many:
                for output_key in output_keys:
                    self._put_to_right(output_key, processed_payload)
            else:
                self._put_to_right(key, processed_payload)

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

        self.post_run()

        exit(0)

    def link(self, stage: Stage, key: str) -> None:
        """
        Connect this stage's output to another stage's input.

        Creates a shared queue between stages and registers it in both stages'
        input/output queue dictionaries.

        Args:
            stage: The downstream stage to connect to.
            key: Stream identifier for this connection. Used to distinguish
                 multiple streams in multi-stream pipelines.

        Raises:
            ValueError: If the stage types are incompatible (e.g., trying to
                       link multiple outputs to a One2One stage).

        Example:
            ```python
            source_stage.link(processor_stage, "stream1")
            processor_stage.link(sink_stage, "stream1")
            ```
        """
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
        """
        Disconnect all queues matching the given stream identifier.

        Closes and removes input/output queues containing the stream_id in their key.
        If all queues are removed and the stage has no remaining connections,
        it will automatically stop.

        Args:
            stream_id: The stream identifier to disconnect. All queues with keys
                      containing this string will be closed and removed.

        Note:
            This is useful for dynamic pipeline reconfiguration, allowing you to
            remove specific streams without stopping the entire pipeline.
        """
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
        """
        Start the stage's processing loop.

        Sets the running flag and starts the worker thread/process.
        The stage will begin processing payloads once started.
        """
        self._running.set()
        self._worker.start()

    def stop(self):
        """
        Signal the stage to stop processing.

        Clears the running flag, which will cause the processing loop to exit
        after the current iteration. Does not wait for shutdown to complete.
        Use join() after stop() to wait for graceful termination.
        """
        logger.info(f"Stopping {self.__class__.__name__}")
        self._running.clear()
        time.sleep(0.1)

    def join(self):
        """
        Wait for the stage to finish processing and shut down.

        Blocks until the worker thread/process completes. If graceful shutdown
        fails, will attempt to terminate/kill the worker process.

        Note:
            Always call stop() before join() to signal termination first.
        """
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
