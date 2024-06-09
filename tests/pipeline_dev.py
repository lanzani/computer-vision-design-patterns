# -*- coding: utf-8 -*-
from computer_vision_design_patterns.pipeline import Payload, ProcessStage, MultiQueueThreadStage


def main():
    cam = ProcessStage(key="0", output_maxsize=15, control_queue=None)
    sink = ProcessStage(key="0", output_maxsize=15, control_queue=None)
    mstage1 = MultiQueueThreadStage(key="0", output_maxsize=15, control_queue=None)
    pstage3 = ProcessStage(key="0", output_maxsize=15, control_queue=None)

    cam.link(sink)
    sink.link(mstage1)
    mstage1.link(pstage3)


if __name__ == "__main__":
    main()
