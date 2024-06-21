# -*- coding: utf-8 -*-
from computer_vision_design_patterns.pipeline import Payload
from computer_vision_design_patterns.pipeline.stage import Stage
import multiprocessing as mp

from computer_vision_design_patterns.pipeline.stage1to1 import Stage1to1


def main():
    p = Payload()
    stage1 = Stage1to1("stage1", output_maxsize=2)

    stage1.output_queue = mp.Queue(maxsize=2)  # tmp

    stage2 = Stage1to1("stage2")

    stage1.put_to_right(p)
    stage1.put_to_right(p)
    stage1.put_to_right(p)
    stage1.put_to_right(p)

    print(stage1.output_queue.qsize())


if __name__ == "__main__":
    main()
