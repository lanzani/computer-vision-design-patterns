# -*- coding: utf-8 -*-
from computer_vision_design_patterns.pipeline import Payload, ProcessStage, MultiQueueThreadStage


def main():
    pstage1 = ProcessStage(key="0", input_max_size=15, control_queue=None)
    pstage2 = ProcessStage(key="0", input_max_size=15, control_queue=None)
    mstage1 = MultiQueueThreadStage(key="0", input_max_size=15, control_queue=None)

    pstage1.link(pstage2)
    pstage1.link(mstage1)


if __name__ == "__main__":
    main()
