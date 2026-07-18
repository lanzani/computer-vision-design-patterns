# -*- coding: utf-8 -*-
"""Integration test for the reference topology (the user's target use case):

4 streams × (camera → pose → fall) with pose fanning into per-apartment
aggregators (streams 1-2 → apartment-1, streams 3-4 → apartment-2),
plus hot add/remove of streams while running.
"""

from __future__ import annotations

import time

from computer_vision_design_patterns.pipeline_v3 import EventPacket, Packet, Supervisor
from computer_vision_design_patterns.pipeline_v3.stage import SinkStage
from computer_vision_design_patterns.pipeline_v3.stages import (
    ApartmentAggregator,
    FallDetectStage,
    PoseStage,
    SyntheticSource,
)


class SnapshotCollect(SinkStage):
    def __init__(self, name: str):
        super().__init__(name=name)
        self.events_in = self.add_input("events", EventPacket)
        self.snapshots: list[dict] = []

    def consume(self, port_name: str, packet: Packet) -> None:
        self.snapshots.append(packet.metadata)

    def stream_sets(self) -> set[tuple[str, ...]]:
        return {tuple(s.get("streams", [])) for s in self.snapshots}

    def all_streams_seen(self) -> set[str]:
        return {s for snap in self.snapshots for s in snap.get("streams", [])}


def add_camera(sup: Supervisor, stream_id: str, apartment: ApartmentAggregator) -> None:
    camera = SyntheticSource(stream_id, fps=30.0, shape=(16, 16, 3))
    pose = PoseStage(f"pose-{stream_id}")
    fall = FallDetectStage(f"fall-{stream_id}")
    sup.add_stream(
        stream_id,
        chain=[camera, pose],
        fanout={pose.poses_out: [fall]},
        attach=[(pose.poses_out, apartment.port_for(stream_id))],
    )


def _wait_until(predicate, timeout=10.0, step=0.05) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if predicate():
            return True
        time.sleep(step)
    return False


def test_four_streams_two_apartments_with_hot_reconfig():
    sup = Supervisor(join_timeout=3.0)

    apartment1 = ApartmentAggregator("apartment-1", apartment_id="apt-1", window_s=5.0)
    apartment2 = ApartmentAggregator("apartment-2", apartment_id="apt-2", window_s=5.0)
    collect1 = SnapshotCollect("collect-1")
    collect2 = SnapshotCollect("collect-2")
    for stage in (apartment1, apartment2, collect1, collect2):
        sup.add_stage(stage)
    sup.chain(apartment1, collect1)
    sup.chain(apartment2, collect2)

    add_camera(sup, "stream1", apartment1)
    add_camera(sup, "stream2", apartment1)
    add_camera(sup, "stream3", apartment2)
    add_camera(sup, "stream4", apartment2)

    assert len(sup) == 4 + 4 * 3  # 4 shared stages + 4 × (camera, pose, fall)

    sup.start()
    try:
        # Both apartments eventually see BOTH of their own streams together.
        assert _wait_until(lambda: ("stream1", "stream2") in collect1.stream_sets())
        assert _wait_until(lambda: ("stream3", "stream4") in collect2.stream_sets())

        # Strict isolation: no cross-apartment leakage.
        assert collect1.all_streams_seen() <= {"stream1", "stream2"}
        assert collect2.all_streams_seen() <= {"stream3", "stream4"}

        # Hot-add stream5 to apartment 2.
        add_camera(sup, "stream5", apartment2)
        assert _wait_until(lambda: ("stream3", "stream4", "stream5") in collect2.stream_sets())

        # Hot-remove stream1: apartment 1 continues on stream2 alone.
        sup.remove_stream("stream1")
        assert _wait_until(lambda: "in-stream1" not in apartment1.inputs)
        marker = len(collect1.snapshots)
        assert _wait_until(lambda: ("stream2",) in {tuple(s.get("streams", [])) for s in collect1.snapshots[marker:]})

        # Everything still healthy.
        stats = sup.stats()
        for name in ("apartment-1", "apartment-2", "pose-stream2", "pose-stream5"):
            assert stats[name].healthy, f"{name} unhealthy"
    finally:
        sup.stop()

    assert not sup.is_running
