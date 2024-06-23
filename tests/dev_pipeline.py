# -*- coding: utf-8 -*-
import time

from computer_vision_design_patterns.pipeline import Payload, StageNtoN
from computer_vision_design_patterns.pipeline.sample_stage import (
    SimpleStreamStage,
    VideoSink,
    DummyStageNtoN,
    DummyStage1to1,
)
import multiprocessing as mp


def dev_1to1():
    output_maxsize = 2
    queue_timeout = 1

    p = Payload()

    stream = SimpleStreamStage("stream", 0, output_maxsize, queue_timeout)
    sink = VideoSink("sink", output_maxsize, queue_timeout)

    stream.link(sink)

    stream.start()
    sink.start()

    time.sleep(10)
    stream.terminate()
    sink.terminate()


def dev_NtoN():
    output_maxsize = 2
    queue_timeout = 1

    p1 = Payload()
    time.sleep(0.0000001)
    p2 = Payload()

    stage1 = DummyStage1to1("stage1", output_maxsize, queue_timeout)
    stage11 = DummyStage1to1("stage11", output_maxsize, queue_timeout)
    stage2 = DummyStageNtoN("stage2", output_maxsize, queue_timeout)

    stage1.link(stage2)
    stage11.link(stage2)

    stage1.put_to_right(p1)
    stage11.put_to_right(p2)

    print(stage2.get_from_left())


if __name__ == "__main__":
    dev_NtoN()
