# -*- coding: utf-8 -*-
import time

from loguru import logger

from computer_vision_design_patterns.pipeline.stage import Stage


class Pipeline:
    """
    Orchestrates multiple stages into a processing pipeline.

    The Pipeline manages the lifecycle of stages and their connections. It provides
    a high-level interface for building, starting, stopping, and reconfiguring
    real-time processing pipelines.

    A pipeline consists of:
    1. Multiple stages (computation units)
    2. Connections between stages (data flow)
    3. Stream identifiers (keys) to distinguish multiple data streams

    The pipeline handles:
    - Stage registration and lifecycle management
    - Starting/stopping all stages

    Args:
        start_sleep_time: Delay in seconds between starting each stage.
                         Allows stages to initialize before receiving data.

    Example:
        ```python
        pipeline = Pipeline()

        # Create stages
        source = VideoSourceStage(camera_id=0, executor=StageExecutor.PROCESS)
        processor = GrayscaleStage(executor=StageExecutor.THREAD)
        sink = DisplayStage(executor=StageExecutor.PROCESS)

        # Add stages to pipeline
        pipeline.add_stage(source)
        pipeline.add_stage(processor)
        pipeline.add_stage(sink)

        # Connect stages
        pipeline.link_stages(source, processor, "stream1")
        pipeline.link_stages(processor, sink, "stream1")

        # Start processing
        pipeline.start()

        try:
            # Pipeline runs until interrupted
            time.sleep(60)
        finally:
            # Clean shutdown
            pipeline.stop_all_stages()
        ```
    """

    def __init__(self, start_sleep_time: float = 1.0):
        self.stages: list[Stage] = []
        self._start_sleep_time = start_sleep_time

    def __len__(self):
        return len(self.stages)

    def add_stage(self, stage: Stage):
        """
        Register a stage with the pipeline.

        Args:
            stage: The stage to add.
        """
        self.stages.append(stage)

    @staticmethod
    def link_stages(from_stage: Stage, to_stage: Stage, key: str):
        """
        Connect two stages in the pipeline.

        Creates a data flow connection from from_stage's output to to_stage's input.

        Args:
            from_stage: The upstream stage (data source).
            to_stage: The downstream stage (data sink).
            key: Stream identifier for this connection.

        Note:
            This is a convenience wrapper around Stage.link().
            Stages must be added to the pipeline before linking.
        """
        from_stage.link(to_stage, key)

    def unlink(self, key: str):
        """
        Remove a stream from the pipeline.

        Disconnects all queues matching the stream key and removes dead stages.

        Args:
            key: Stream identifier to remove. All stages with queues containing
                 this key will be disconnected.
        """
        for stage in self.stages:
            stage.unlink(key)

        # Remove not alive stages
        self.stages = [stage for stage in self.stages if stage.is_alive()]

    def start(self):
        """
        Start all stages in the pipeline.

        Stages are started sequentially with a delay between each to allow
        proper initialization. Only stages that are not already running will be started.
        """
        for stage in self.stages:
            try:
                if not stage.is_alive():
                    stage.start()
                    time.sleep(self._start_sleep_time)
            except RuntimeError as e:
                logger.warning(e)

    def stop(self):
        """
        Stop all stages gracefully.

        Stops stages in reverse order (sinks first, sources last) to allow
        in-flight data to be processed. Waits for each stage to finish.
        """
        for stage in reversed(self.stages):
            stage.stop()

        for stage in reversed(self.stages):
            stage.join()

    def flush(self):
        """
        Remove all stages from the pipeline.

        Clears the stage list. Stages are not stopped - use stop() or stop_all_stages()
        before flushing if you want to cleanly shut down.
        """
        self.stages = []
