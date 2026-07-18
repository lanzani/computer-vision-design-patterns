# -*- coding: utf-8 -*-
"""Pipeline v3 — robust real-time CV pipeline framework.

Core ideas:

- ``Packet`` subclasses with ``stream_id`` inside (no stringly-keyed routing)
- Typed ``Port``s; fan-in/fan-out is a property of the wiring, not the stage
- Bounded ``Channel``s (``LATEST_ONLY`` default for video) with sentinel drain
- ``Stage``: pure ``setup``/``process``/``teardown`` — no queues or workers
- ``StageRunner``: spawn-safe worker loop with error backoff and pacing
- ``Supervisor``: readiness, health + restart policy, hot stream add/remove
- ``FrameWriter``/``FrameReader``: shared-memory frames on process edges
"""

from computer_vision_design_patterns.pipeline_v3.channel import (
    Channel,
    ChannelClosed,
    OverflowPolicy,
    ProcessChannel,
    ThreadChannel,
    make_channel,
)
from computer_vision_design_patterns.pipeline_v3.framestore import FrameReader, FrameWriter
from computer_vision_design_patterns.pipeline_v3.graph import (
    Edge,
    GraphValidationError,
    PipelineGraph,
)
from computer_vision_design_patterns.pipeline_v3.packet import (
    SENTINEL,
    EventPacket,
    FramePacket,
    FrameRef,
    Packet,
    PosePacket,
)
from computer_vision_design_patterns.pipeline_v3.port import Port
from computer_vision_design_patterns.pipeline_v3.runner import StageRunner
from computer_vision_design_patterns.pipeline_v3.stage import (
    AggregatorStage,
    ErrorPolicy,
    ExecutorType,
    SinkStage,
    SourceStage,
    Stage,
    StageMetrics,
    StopStage,
)
from computer_vision_design_patterns.pipeline_v3.supervisor import PipelineEvent, Supervisor

__all__ = [
    # packets
    "SENTINEL",
    "Packet",
    "FrameRef",
    "FramePacket",
    "PosePacket",
    "EventPacket",
    # ports / channels
    "Port",
    "Channel",
    "ChannelClosed",
    "OverflowPolicy",
    "ThreadChannel",
    "ProcessChannel",
    "make_channel",
    # stages
    "Stage",
    "SourceStage",
    "SinkStage",
    "AggregatorStage",
    "ExecutorType",
    "ErrorPolicy",
    "StageMetrics",
    "StopStage",
    "StageRunner",
    # orchestration
    "PipelineGraph",
    "Edge",
    "GraphValidationError",
    "Supervisor",
    "PipelineEvent",
    # frame transport
    "FrameWriter",
    "FrameReader",
]
