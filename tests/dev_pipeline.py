# -*- coding: utf-8 -*-
import time

from computer_vision_design_patterns.pipeline import Pipeline
from computer_vision_design_patterns.pipeline.sample_stage import SimpleStreamStage, VideoSink
from computer_vision_design_patterns.pipeline.stage import StageExecutor


def main():
    p = Pipeline()

    stream = SimpleStreamStage(StageExecutor.PROCESS, 0)
    sink = VideoSink(StageExecutor.PROCESS)

    stream.link(sink, "stream1")

    stream.start()
    sink.start()

    time.sleep(5)
    stream.stop()
    sink.stop()


if __name__ == "__main__":
    main()
