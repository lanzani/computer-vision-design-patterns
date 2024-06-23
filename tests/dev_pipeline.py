# -*- coding: utf-8 -*-
import time

from computer_vision_design_patterns.pipeline import Payload
from computer_vision_design_patterns.pipeline.sample_stage import SimpleStreamStage, VideoSink


def main():
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


if __name__ == "__main__":
    main()
