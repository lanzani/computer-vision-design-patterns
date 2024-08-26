# -*- coding: utf-8 -*-
import multiprocessing
import time

from computer_vision_design_patterns.pipeline import Pipeline
from computer_vision_design_patterns.pipeline.sample_stage import (
    SimpleStreamStage,
    VideoSink,
    RGB2GRAYStage,
    SwitchStage,
)
from computer_vision_design_patterns.pipeline.stage import StageExecutor


# TODO
#  - Compile the code to improve performance?
#  - Test memory usage
#  - How to safely stop all the stages?
#  - Add actions on link and unlink


def main():
    p = Pipeline()

    stream1 = SimpleStreamStage(0, StageExecutor.THREAD, output_maxsize=10, queue_timeout=2)
    stream2 = SimpleStreamStage(1, StageExecutor.THREAD, output_maxsize=10, queue_timeout=2)

    dummy_operation = RGB2GRAYStage(StageExecutor.PROCESS)
    # switch1 = SwitchStage(StageExecutor.PROCESS, output_maxsize=10, queue_timeout=2)
    # switch2 = SwitchStage(StageExecutor.PROCESS, output_maxsize=10, queue_timeout=2)

    sink = VideoSink(StageExecutor.PROCESS)
    sink2 = VideoSink(StageExecutor.PROCESS)

    sink3 = VideoSink(StageExecutor.PROCESS)
    sink4 = VideoSink(StageExecutor.PROCESS)

    p.add_stage(stream1)
    p.add_stage(stream2)
    p.add_stage(dummy_operation)
    # p.add_stage(switch1)
    # p.add_stage(switch2)
    p.add_stage(sink)
    p.add_stage(sink2)
    p.add_stage(sink3)
    p.add_stage(sink4)

    p.link_stages(stream1, dummy_operation, "stream1")
    p.link_stages(dummy_operation, sink, "stream1")

    p.link_stages(stream2, dummy_operation, "stream2")
    p.link_stages(dummy_operation, sink2, "stream2")

    p.start()

    time.sleep(10)

    # p.unlink("stream1")
    p.stop()

    # time.sleep(40)

    # p.poison_pill()


def dev_queue():
    q = multiprocessing.Queue(maxsize=10)
    q.put("hello")

    q.close()

    try:
        q.get()
    except ValueError:
        print("Queue closed")


if __name__ == "__main__":
    main()
