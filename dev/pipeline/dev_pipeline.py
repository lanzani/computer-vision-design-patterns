# -*- coding: utf-8 -*-
import multiprocessing
import time

from loguru import logger

from computer_vision_design_patterns.pipeline import Pipeline
from computer_vision_design_patterns.pipeline.sample_stage import (
    RGB2GRAYStage,
    SimpleStreamStage,
    SwitchStage,
    VideoSink,
)
from computer_vision_design_patterns.pipeline.stage import StageExecutor


def main():
    p = Pipeline()

    daemon = True
    output_queues_maxsize = 10
    input_queues_timeout = 0.05
    output_queues_timeout = 0.05

    stream1 = SimpleStreamStage(
        0,
        StageExecutor.THREAD,
        daemon=daemon,
        output_queues_maxsize=output_queues_maxsize,
        input_queues_timeout=input_queues_timeout,
        output_queues_timeout=output_queues_timeout,
    )
    sink = VideoSink(
        StageExecutor.THREAD,
        daemon=daemon,
        input_queues_timeout=input_queues_timeout,
    )

    p.add_stage(stream1)
    p.add_stage(sink)

    p.link_stages(stream1, sink, "stream1")

    logger.info(f"starting pipeline with {len(p)} stages")

    p.start()
    time.sleep(2)
    p.stop()


#     dummy_operation = RGB2GRAYStage(StageExecutor.THREAD)
#     switch1 = SwitchStage(StageExecutor.PROCESS, output_maxsize=10, queue_timeout=2)
#     switch2 = SwitchStage(StageExecutor.PROCESS, output_maxsize=10, queue_timeout=2)

#     sink = VideoSink(StageExecutor.PROCESS)
#     sink2 = VideoSink(StageExecutor.PROCESS)

#     sink3 = VideoSink(StageExecutor.PROCESS)
#     sink4 = VideoSink(StageExecutor.PROCESS)

#     p.add_stage(stream1)
#     p.add_stage(stream2)
#     p.add_stage(dummy_operation)
#     p.add_stage(switch1)
#     p.add_stage(switch2)
#     p.add_stage(sink)
#     p.add_stage(sink2)
#     p.add_stage(sink3)
#     p.add_stage(sink4)

#     p.link_stages(stream1, dummy_operation, "stream1")
#     p.link_stages(dummy_operation, switch1, "stream1")
#     p.link_stages(switch1, sink, "stream1")
#     p.link_stages(switch1, sink2, "stream1")

#     p.link_stages(stream2, dummy_operation, "stream2")
#     p.link_stages(dummy_operation, switch2, "stream2")
#     p.link_stages(switch2, sink2, "stream2")
#     p.link_stages(switch2, sink4, "stream2")

#     p.start()

#     try:
#         time.sleep(10)
#         p.unlink("stream1")
#         time.sleep(10)
#     finally:
#         p.stop()

#     for stage in p.stages:
#         print(stage)
#         print(stage.is_alive())
#         print(stage._running.is_set())
#         print(stage.input_queues)
#         print(stage._output_queues)


# def dev_queue():
#     q = multiprocessing.Queue(maxsize=10)
#     q.put("hello")

#     q.close()

#     try:
#         q.get()
#     except ValueError:
#         print("Queue closed")


if __name__ == "__main__":
    main()
