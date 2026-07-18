# -*- coding: utf-8 -*-
"""The reference topology: 4 camera streams, 2 apartments — fully headless.

    stream1 ─ pose1 ─┬─ fall1
                     ├─ (sink omitted headless)
                     └─► apartment-1 ─► alert sink
    stream2 ─ pose2 ─┬─ fall2
                     └─► apartment-1
    stream3 ─ pose3 ─┬─ fall3
                     └─► apartment-2 ─► alert sink
    stream4 ─ pose4 ─┬─ fall4
                     └─► apartment-2

Concepts shown:
- add_stream(): one call per camera, identical before start and at runtime
- AggregatorStage.port_for(): dynamic fan-in ports per stream
- hot add (stream5) and hot remove (stream1) while running
- on_event callback and stats()

Run:  uv run python dev/pipeline_v3/dev_02_apartments.py
"""

from __future__ import annotations

import time

from loguru import logger

from computer_vision_design_patterns.pipeline_v3 import (
    EventPacket,
    Packet,
    PipelineEvent,
    SinkStage,
    Supervisor,
)
from computer_vision_design_patterns.pipeline_v3.stages import (
    ApartmentAggregator,
    FallDetectStage,
    PoseStage,
    SyntheticSource,
)


class AlertSink(SinkStage):
    """Collects apartment snapshots (stand-in for MQTT / DB / webhook)."""

    def __init__(self, name: str):
        super().__init__(name=name)
        self.events_in = self.add_input("events", EventPacket)
        self.count = 0

    def consume(self, port_name: str, packet: Packet) -> None:
        self.count += 1
        if self.count % 20 == 0:
            logger.info(f"[{self.name}] #{self.count}: {packet.metadata}")


def add_camera(sup: Supervisor, stream_id: str, apartment: ApartmentAggregator) -> None:
    """One call wires a full camera branch — used for both startup and hot-add."""
    camera = SyntheticSource(stream_id, fps=15.0)
    pose = PoseStage(f"pose-{stream_id}")
    fall = FallDetectStage(f"fall-{stream_id}")

    sup.add_stream(
        stream_id,
        chain=[camera, pose],
        fanout={pose.poses_out: [fall]},
        attach=[(pose.poses_out, apartment.port_for(stream_id))],
    )


def on_event(event: PipelineEvent) -> None:
    logger.info(f"EVENT {event.kind} stage={event.stage_name} stream={event.stream_id}")


def main() -> None:
    sup = Supervisor(on_event=on_event)

    # Shared analysis stages — THREAD so they accept hot-attached streams.
    apartment1 = ApartmentAggregator("apartment-1", apartment_id="apt-1")
    apartment2 = ApartmentAggregator("apartment-2", apartment_id="apt-2")
    alerts1 = AlertSink("alerts-apt-1")
    alerts2 = AlertSink("alerts-apt-2")
    for stage in (apartment1, apartment2, alerts1, alerts2):
        sup.add_stage(stage)
    sup.chain(apartment1, alerts1)
    sup.chain(apartment2, alerts2)

    # Four cameras, two per apartment (the image topology).
    add_camera(sup, "stream1", apartment1)
    add_camera(sup, "stream2", apartment1)
    add_camera(sup, "stream3", apartment2)
    add_camera(sup, "stream4", apartment2)

    sup.start()
    try:
        time.sleep(3.0)
        _print_stats(sup, "steady state, 4 streams")

        logger.info(">>> hot-adding stream5 to apartment-2")
        add_camera(sup, "stream5", apartment2)
        time.sleep(2.0)
        _print_stats(sup, "after hot-add")

        logger.info(">>> hot-removing stream1 from apartment-1")
        sup.remove_stream("stream1")
        time.sleep(2.0)
        _print_stats(sup, "after hot-remove")

        logger.info(f"apartment-1 alerts: {alerts1.count}, apartment-2 alerts: {alerts2.count}")
    finally:
        sup.stop()


def _print_stats(sup: Supervisor, label: str) -> None:
    logger.info(f"--- stats: {label} ---")
    for name, m in sorted(sup.stats().items()):
        logger.info(f"  {name:<18} processed={m.processed:<6} fps={m.fps:<5.1f} drops={m.drops:<4} healthy={m.healthy}")


if __name__ == "__main__":
    main()
