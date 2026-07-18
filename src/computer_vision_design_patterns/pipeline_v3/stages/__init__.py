# -*- coding: utf-8 -*-
"""Reference / stub stages for pipeline_v3."""

from computer_vision_design_patterns.pipeline_v3.stages.apartment import ApartmentAggregator
from computer_vision_design_patterns.pipeline_v3.stages.camera import CameraSource
from computer_vision_design_patterns.pipeline_v3.stages.fall import FallDetectStage
from computer_vision_design_patterns.pipeline_v3.stages.pose import PoseStage
from computer_vision_design_patterns.pipeline_v3.stages.synthetic import SyntheticSource
from computer_vision_design_patterns.pipeline_v3.stages.video_sink import VideoSink

__all__ = [
    "CameraSource",
    "SyntheticSource",
    "VideoSink",
    "PoseStage",
    "FallDetectStage",
    "ApartmentAggregator",
]
