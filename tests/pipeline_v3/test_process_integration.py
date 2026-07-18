# -*- coding: utf-8 -*-
"""End-to-end tests with a real spawned child process.

These prove the claims that were untested in the first v3 iteration:
- PROCESS stages actually start under the spawn method (Windows-compatible)
- frames cross process boundaries via shared memory and arrive intact
- metrics flow back from the child over the control bus
- shutdown is clean (no hung processes)
"""

from __future__ import annotations

import os
import time

import numpy as np

from computer_vision_design_patterns.pipeline_v3 import (
    ExecutorType,
    Packet,
    PosePacket,
    Supervisor,
)
from computer_vision_design_patterns.pipeline_v3.stage import SinkStage
from computer_vision_design_patterns.pipeline_v3.stages import PoseStage, SyntheticSource

FILL = 42


class PoseCollect(SinkStage):
    def __init__(self):
        super().__init__(name="pose-collect")
        self.inp = self.add_input("in", PosePacket)
        self.received: list[PosePacket] = []

    def consume(self, port_name: str, packet: Packet) -> None:
        self.received.append(packet)


def _wait_until(predicate, timeout=20.0, step=0.05) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if predicate():
            return True
        time.sleep(step)
    return False


def test_process_stage_end_to_end():
    """THREAD source → PROCESS pose → THREAD sink, frames via shared memory."""
    sup = Supervisor(join_timeout=8.0)

    source = SyntheticSource("cam1", fps=30.0, shape=(24, 32, 3), fill_value=FILL)
    pose = PoseStage("pose-proc", executor=ExecutorType.PROCESS)
    sink = PoseCollect()

    for stage in (source, pose, sink):
        sup.add_stage(stage)
    sup.chain(source, pose, sink)

    sup.start()
    try:
        assert _wait_until(lambda: len(sink.received) >= 5), "no packets crossed the process"

        packet = sink.received[-1]
        # The frame made two shared-memory hops (parent→child, child→parent)
        # and must arrive intact, as a plain numpy array, with no ref leaking.
        assert packet.frame_ref is None
        assert isinstance(packet.frame, np.ndarray)
        assert packet.frame.shape == (24, 32, 3)
        assert int(packet.frame[0, 0, 0]) == FILL

        # Metrics from the child arrived over the control bus with a child pid.
        assert _wait_until(lambda: sup.stats().get("pose-proc", None) is not None)
        assert _wait_until(lambda: sup.stats()["pose-proc"].processed > 0)
        assert sup.stats()["pose-proc"].pid not in (0, os.getpid())
    finally:
        t0 = time.time()
        sup.stop()
        stop_duration = time.time() - t0

    # Clean shutdown: no hung child, join within the timeout budget.
    assert stop_duration < 15.0
    assert all(not r.is_alive() for r in sup._runners.values()) or not sup._runners
