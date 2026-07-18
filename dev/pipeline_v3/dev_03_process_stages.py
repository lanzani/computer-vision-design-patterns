# -*- coding: utf-8 -*-
"""Heavy stages in child processes with shared-memory frame transport.

A THREAD camera feeds a PROCESS "pose" stage (simulating a heavy model that
needs its own core/GIL). Frames cross the process boundary through shared
memory (FrameWriter/FrameReader inside the channel) — no pickling of pixels.

Concepts shown:
- ExecutorType.PROCESS: the stage runs in a spawned child (see the pid column)
- transparent shared-memory frames: stages just read packet.frame
- metrics flowing back from the child over the control bus

Run:  uv run python dev/pipeline_v3/dev_03_process_stages.py
"""

from __future__ import annotations

import os
import time

from loguru import logger

from computer_vision_design_patterns.pipeline_v3 import (
    ExecutorType,
    Packet,
    SinkStage,
    Supervisor,
)
from computer_vision_design_patterns.pipeline_v3.packet import FramePacket, PosePacket
from computer_vision_design_patterns.pipeline_v3.stage import Stage
from computer_vision_design_patterns.pipeline_v3.stages import SyntheticSource


class HeavyPoseStage(Stage):
    """Simulates a CPU-heavy model. Runs in its own process.

    NOTE: PROCESS stages are pickled into the child at start — construct them
    with picklable state only and open models/resources in setup().
    """

    def __init__(self, name: str = "heavy-pose"):
        super().__init__(name=name, executor=ExecutorType.PROCESS)
        self.frames_in = self.add_input("frames", FramePacket)
        self.poses_out = self.add_output("poses", PosePacket)

    def setup(self) -> None:
        logger.info(f"HeavyPoseStage running in pid={os.getpid()}")

    def process(self, inputs: dict[str, Packet]) -> dict[str, Packet | None] | None:
        packet = inputs.get("frames")
        if not isinstance(packet, FramePacket):
            return None
        # packet.frame is a real numpy array here, copied out of shared memory.
        mean = float(packet.frame.mean())
        return {
            "poses": PosePacket(
                stream_id=packet.stream_id,
                seq=packet.seq,
                ts_capture=packet.ts_capture,
                keypoints=((mean, mean, 1.0),),
            )
        }


class PoseLogSink(SinkStage):
    def __init__(self):
        super().__init__(name="pose-log")
        self.poses_in = self.add_input("poses", PosePacket)
        self.received = 0

    def consume(self, port_name: str, packet: Packet) -> None:
        self.received += 1
        if self.received % 30 == 0:
            logger.info(f"pose #{packet.seq} keypoints={packet.keypoints}")


def main() -> None:
    logger.info(f"main process pid={os.getpid()}")

    sup = Supervisor()
    camera = SyntheticSource("cam1", fps=30.0, shape=(480, 640, 3))
    pose = HeavyPoseStage()
    sink = PoseLogSink()

    for stage in (camera, pose, sink):
        sup.add_stage(stage)
    sup.chain(camera, pose, sink)

    with sup:
        time.sleep(5.0)
        for name, m in sup.stats().items():
            logger.info(
                f"{name:<12} pid={m.pid:<7} processed={m.processed:<6} "
                f"fps={m.fps:<5.1f} latency={m.last_latency_ms:.2f}ms"
            )


if __name__ == "__main__":
    main()
