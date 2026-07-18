# -*- coding: utf-8 -*-
"""Stub fall-detection stage driven by PosePacket input."""

from __future__ import annotations

from computer_vision_design_patterns.pipeline_v3.packet import EventPacket, Packet, PosePacket
from computer_vision_design_patterns.pipeline_v3.stage import ExecutorType, Stage


class FallDetectStage(Stage):
    """Single-stream fall detection stub.

    Emits an ``EventPacket`` when ``score`` crosses the threshold. Its output
    port may be left unconnected (events are then dropped) or wired to an
    alerting sink. Replace ``score`` with your real classifier.
    """

    def __init__(
        self,
        name: str = "fall",
        executor: ExecutorType = ExecutorType.THREAD,
        confidence_threshold: float = 0.7,
    ):
        super().__init__(name=name, executor=executor)
        self.confidence_threshold = confidence_threshold
        self.poses_in = self.add_input("poses", PosePacket)
        self.events_out = self.add_output("events", EventPacket)

    def process(self, inputs: dict[str, Packet]) -> dict[str, Packet | None] | None:
        packet = inputs.get("poses")
        if not isinstance(packet, PosePacket):
            return None

        confidence = self.score(packet)
        if confidence < self.confidence_threshold:
            return None

        return {
            "events": EventPacket(
                stream_id=packet.stream_id,
                seq=packet.seq,
                ts_capture=packet.ts_capture,
                event_type="fall",
                confidence=confidence,
                metadata={"bbox": packet.bbox},
            )
        }

    def score(self, packet: PosePacket) -> float:
        """Override with a real fall classifier. Stub never fires."""
        return 0.0
