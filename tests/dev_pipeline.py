# -*- coding: utf-8 -*-
import time
from loguru import logger

from computer_vision_design_patterns.pipeline import Pipeline
from computer_vision_design_patterns.pipeline.sample_stage import (
    SimpleStreamStage,
    VideoSink,
    RGB2GRAYStage,
    SwitchStage,
)
from computer_vision_design_patterns.pipeline.stage import StageExecutor


def main():
    logger.info("Starting pipeline setup")
    p = Pipeline()

    stream1 = SimpleStreamStage(0, StageExecutor.THREAD, output_maxsize=10, queue_timeout=2)
    stream2 = SimpleStreamStage(1, StageExecutor.THREAD, output_maxsize=10, queue_timeout=2)

    dummy_operation = RGB2GRAYStage(StageExecutor.PROCESS)
    switch1 = SwitchStage(StageExecutor.PROCESS, output_maxsize=10, queue_timeout=2)
    switch2 = SwitchStage(StageExecutor.PROCESS, output_maxsize=10, queue_timeout=2)

    sink = VideoSink(StageExecutor.THREAD)
    sink2 = VideoSink(StageExecutor.THREAD)

    sink3 = VideoSink(StageExecutor.PROCESS)
    sink4 = VideoSink(StageExecutor.PROCESS)

    p.add_stage(stream1)
    p.add_stage(stream2)
    p.add_stage(dummy_operation)
    p.add_stage(switch1)
    p.add_stage(switch2)
    p.add_stage(sink)
    p.add_stage(sink2)
    p.add_stage(sink3)
    p.add_stage(sink4)

    p.link_stages(stream1, dummy_operation, "stream1")
    p.link_stages(dummy_operation, switch1, "stream1")
    p.link_stages(switch1, sink, "stream1")
    p.link_stages(switch1, sink3, "stream1")

    p.link_stages(stream2, dummy_operation, "stream2")
    p.link_stages(dummy_operation, switch2, "stream2")
    p.link_stages(switch2, sink2, "stream2")
    p.link_stages(switch2, sink4, "stream2")

    logger.info("Starting pipeline")
    p.start()

    logger.info("Pipeline running, waiting for 10 seconds")
    time.sleep(10)

    logger.info("Stopping pipeline")
    p.stop()

    logger.info("Pipeline stopped, exiting main function")


if __name__ == "__main__":
    main()
