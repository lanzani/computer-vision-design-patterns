# -*- coding: utf-8 -*-
"""Stub pose-detection stage (replace ``detect`` with a real model)."""

from __future__ import annotations

from computer_vision_design_patterns.pipeline_v3.packet import FramePacket, Packet, PosePacket
from computer_vision_design_patterns.pipeline_v3.stage import ExecutorType, Stage


class PoseStage(Stage):
    """Single-stream pose detection stub.

    Forwards the frame (for downstream sinks) and emits keypoints. Override
    ``detect`` with MediaPipe / YOLO-Pose / etc.; heavy models should run with
    ``executor=ExecutorType.PROCESS`` — frames then travel via shared memory.
    """

    def __init__(
        self,
        name: str = "pose",
        executor: ExecutorType = ExecutorType.THREAD,
    ):
        super().__init__(name=name, executor=executor)
        self.frames_in = self.add_input("frames", FramePacket)
        self.poses_out = self.add_output("poses", PosePacket)

    def process(self, inputs: dict[str, Packet]) -> dict[str, Packet | None] | None:
        packet = inputs.get("frames")
        if not isinstance(packet, FramePacket):
            return None

        keypoints, bbox = self.detect(packet)
        return {
            "poses": PosePacket(
                stream_id=packet.stream_id,
                seq=packet.seq,
                ts_capture=packet.ts_capture,
                keypoints=keypoints,
                bbox=bbox,
                frame=packet.frame,
            )
        }

    def detect(
        self, packet: FramePacket
    ) -> tuple[tuple[tuple[float, float, float], ...], tuple[float, float, float, float] | None]:
        """Override with a real pose model. Stub returns no keypoints."""
        return (), None
