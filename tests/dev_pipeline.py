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
#  - Any better way then copy the queues dictionaries every time?
#  -- change 'for' level to reduce stage hold time, processo queue per queue and not evey at the same time (measure the pipeline time first)
#     iterare solo le chiavi delle code e ottenerle con dict.get(key) per evitare di copiare le code.
#     es:
# def run(self):
#    for key in list(self.input_queues):  # copy only the keys
#        payload = get_payload(key)  # <- queue = self.input_queues.get(key), queue.get()...
#        processed_payload = process(payload)
#        put_payload(processed_payload, key)  # <- queue = self.output.get(key), queue.put(processed_payload)...


def main():
    p = Pipeline()

    stream1 = SimpleStreamStage(0, StageExecutor.PROCESS, output_maxsize=10, queue_timeout=2)
    stream2 = SimpleStreamStage(1, StageExecutor.PROCESS, output_maxsize=10, queue_timeout=2)

    dummy_operation = RGB2GRAYStage(StageExecutor.THREAD)
    switch1 = SwitchStage(StageExecutor.PROCESS, output_maxsize=10, queue_timeout=2)
    switch2 = SwitchStage(StageExecutor.PROCESS, output_maxsize=10, queue_timeout=2)

    sink = VideoSink(StageExecutor.PROCESS)
    sink2 = VideoSink(StageExecutor.PROCESS)

    sink3 = VideoSink(StageExecutor.PROCESS)
    sink4 = VideoSink(StageExecutor.PROCESS)

    p.add_stage(stream1)
    p.add_stage(stream2)
    p.add_stage(dummy_operation)
    p.add_stage(switch1)
    p.add_stage(switch2)
    p.add_stage(sink)
    p.add_stage(sink2)
    p.add_stage(sink3)
    p.add_stage(sink4)

    p.link_stages(stream1, dummy_operation, "stream1")
    p.link_stages(dummy_operation, switch1, "stream1")
    p.link_stages(switch1, sink, "stream1")
    p.link_stages(switch1, sink2, "stream1")

    p.link_stages(stream2, dummy_operation, "stream2")
    p.link_stages(dummy_operation, switch2, "stream2")
    p.link_stages(switch2, sink2, "stream2")
    p.link_stages(switch2, sink4, "stream2")

    p.start()

    try:
        time.sleep(10)
        p.unlink("stream1")
        time.sleep(20)
    finally:
        p.stop_all_stages()


    for stage in p.stages:
        print(stage)
        print(stage.is_alive())
        print(stage._running.is_set())
        print(stage.input_queues)
        print(stage._output_queues)


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
