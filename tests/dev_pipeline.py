# -*- coding: utf-8 -*-
from computer_vision_design_patterns.pipeline import Payload, ProcessStage, MultiQueueThreadStage


def main():
    cam = ProcessStage(key="0", output_maxsize=15, control_queue=None)
    sink = ProcessStage(key="0", output_maxsize=15, control_queue=None)
    pose = MultiQueueThreadStage(key="0", output_maxsize=15, control_queue=None)
    fall = MultiQueueThreadStage(key="0", output_maxsize=15, control_queue=None)

    cam.link(sink)
    sink.link(pose)
    pose.link(fall)


if __name__ == "__main__":
    main()
