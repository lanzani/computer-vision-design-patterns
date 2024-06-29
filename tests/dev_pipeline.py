# -*- coding: utf-8 -*-
import time

from computer_vision_design_patterns.pipeline import Payload
from computer_vision_design_patterns.pipeline.sample_stage import (
    SimpleStreamStage,
    VideoSink,
    RGB2GRAYStage,
    SwitchStage,
)

output_maxsize = 2
queue_timeout = 1


def dev_1to1():
    p = Payload()

    stream = SimpleStreamStage("stream", 0, output_maxsize, queue_timeout)
    sink = VideoSink("sink", queue_timeout)

    stream.link(sink)

    stream.start()
    sink.start()

    time.sleep(10)
    stream.terminate()
    sink.terminate()


def dev_NtoN():
    p = Payload()

    data_flow_key1 = "stream1"
    data_flow_key2 = "stream2"

    stream = SimpleStreamStage(data_flow_key1, 0, output_maxsize, queue_timeout)
    stream2 = SimpleStreamStage(data_flow_key2, 1, output_maxsize, queue_timeout)

    rgb_to_gray = RGB2GRAYStage("rgb_to_gray", output_maxsize, queue_timeout)

    sink = VideoSink(data_flow_key1, queue_timeout)
    sink2 = VideoSink(data_flow_key2, queue_timeout)

    stream.link(rgb_to_gray)
    stream2.link(rgb_to_gray)
    rgb_to_gray.link(sink)
    rgb_to_gray.link(sink2)

    stream.start()
    stream2.start()
    rgb_to_gray.start()
    sink.start()
    sink2.start()


def dev_1toN():
    stream1 = SimpleStreamStage("stream1", 0, output_maxsize, queue_timeout)
    switch = SwitchStage("stream1", output_maxsize, queue_timeout)

    # rgb_to_gray = RGB2GRAYStage("rgb_to_gray", output_maxsize, queue_timeout)

    sink1 = VideoSink("stream1", queue_timeout)
    sink2 = VideoSink("stream1", queue_timeout)

    stream1.link(switch)
    switch.link(sink1)
    switch.link(sink2)
    # rgb_to_gray.link(sink2)

    stream1.start()
    switch.start()
    sink1.start()
    sink2.start()

    # rgb_to_gray.start()


if __name__ == "__main__":
    dev_1toN()
