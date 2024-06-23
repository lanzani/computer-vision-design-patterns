# -*- coding: utf-8 -*-
from computer_vision_design_patterns.pipeline import Payload
from computer_vision_design_patterns.pipeline.stage import Stage
import multiprocessing as mp

from computer_vision_design_patterns.pipeline.stage1to1 import Stage1to1


def main():
    output_maxsize = 2
    queue_timeout = 1

    p = Payload()
    stage1 = Stage1to1("stage1", output_maxsize=output_maxsize, queue_timeout=queue_timeout)
    stage2 = Stage1to1("stage2", output_maxsize=output_maxsize, queue_timeout=queue_timeout)

    stage1.link(stage2)

    stage1.put_to_right(p)
    stage1.put_to_right(p)
    stage1.put_to_right(p)
    print(stage2.get_from_left())
    print(stage2.get_from_left())
    print(stage2.get_from_left())
    print(stage2.get_from_left())
    print(stage2.get_from_left())


if __name__ == "__main__":
    main()
