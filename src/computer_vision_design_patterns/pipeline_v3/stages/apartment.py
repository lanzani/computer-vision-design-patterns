# -*- coding: utf-8 -*-
"""Multi-stream apartment aggregator — time-window fan-in example."""

from __future__ import annotations

from computer_vision_design_patterns.pipeline_v3.packet import EventPacket, Packet, PosePacket
from computer_vision_design_patterns.pipeline_v3.stage import AggregatorStage, ExecutorType


class ApartmentAggregator(AggregatorStage):
    """Aggregates pose packets from all cameras of one apartment.

    Input ports are created with ``port_for(stream_id)``, so cameras can be
    attached and removed at runtime; buffers are freed automatically when a
    stream goes away. Keep this stage on ``ExecutorType.THREAD`` so it can
    accept hot-attached streams.
    """

    def __init__(
        self,
        name: str = "apartment",
        apartment_id: str = "apt-0",
        window_s: float = 0.5,
        executor: ExecutorType = ExecutorType.THREAD,
    ):
        super().__init__(name=name, executor=executor, window_s=window_s, strip_frames=True)
        self.apartment_id = apartment_id
        self.summary_out = self.add_output("summary", EventPacket)

    def aggregate(self, aligned: dict[str, Packet]) -> dict[str, Packet | None] | None:
        streams: list[str] = []
        people = 0
        for packet in aligned.values():
            if isinstance(packet, PosePacket):
                streams.append(packet.stream_id)
                if packet.keypoints:
                    people += 1

        return {
            "summary": EventPacket(
                stream_id=self.apartment_id,
                event_type="apartment_snapshot",
                confidence=1.0,
                metadata={
                    "streams": sorted(streams),
                    "people_estimate": people,
                },
            )
        }
