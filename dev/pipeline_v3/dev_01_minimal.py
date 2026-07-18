# -*- coding: utf-8 -*-
"""Minimal pipeline: one synthetic camera → one logging sink.

This is the smallest possible v3 pipeline and the recommended starting point.

Concepts shown:
- SourceStage / SinkStage subclasses (pure logic, no threads or queues)
- Supervisor.chain() for linear wiring
- stats() snapshots

Run:  uv run python dev/pipeline_v3/dev_01_minimal.py
"""

from __future__ import annotations

import time

from loguru import logger

from computer_vision_design_patterns.pipeline_v3 import Packet, SinkStage, Supervisor
from computer_vision_design_patterns.pipeline_v3.packet import FramePacket
from computer_vision_design_patterns.pipeline_v3.stages import SyntheticSource


class LogSink(SinkStage):
    """Prints one line per received frame packet (throttled)."""

    def __init__(self):
        super().__init__(name="log-sink")
        # Declare what this stage accepts. FramePacket → the graph validator
        # rejects wiring anything else into this port.
        self.frames_in = self.add_input("frames", FramePacket)

    def consume(self, port_name: str, packet: Packet) -> None:
        if packet.seq % 30 == 0:
            logger.info(f"frame #{packet.seq} from {packet.stream_id!r}, shape={packet.frame.shape}")


def main() -> None:
    sup = Supervisor()

    camera = SyntheticSource("cam1", fps=30.0)
    sink = LogSink()

    sup.add_stage(camera)
    sup.add_stage(sink)
    sup.chain(camera, sink)  # single output → single input, LATEST_ONLY by default

    with sup:  # start() on enter, stop() on exit — always shuts down cleanly
        time.sleep(3.0)
        for name, m in sup.stats().items():
            logger.info(f"{name}: processed={m.processed} fps={m.fps:.1f} healthy={m.healthy}")


if __name__ == "__main__":
    main()
