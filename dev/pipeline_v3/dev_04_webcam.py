# -*- coding: utf-8 -*-
"""Real webcam → pose stub → display. Requires a camera.

Concepts shown:
- CameraSource with automatic reconnect (unplug/replug survives)
- VideoSink: press 'q' in the window to stop that sink gracefully
- restart policy: kill the window and watch the supervisor NOT restart it
  (StopStage = intentional), while a crashing stage would be restarted

Run:  uv run python dev/pipeline_v3/dev_04_webcam.py
"""

from __future__ import annotations

import time

from loguru import logger

from computer_vision_design_patterns.pipeline_v3 import Supervisor
from computer_vision_design_patterns.pipeline_v3.stages import CameraSource, PoseStage, VideoSink


def main() -> None:
    sup = Supervisor(on_event=lambda e: logger.info(f"EVENT {e.kind} stage={e.stage_name}"))

    camera = CameraSource("webcam", source=0, target_fps=30.0)
    pose = PoseStage("pose-webcam")
    sink = VideoSink("display", quit_key="q")

    for stage in (camera, pose, sink):
        sup.add_stage(stage)
    sup.chain(camera, pose, sink)

    logger.info("Press 'q' in the video window to close it; Ctrl+C to stop the pipeline")
    sup.start()
    try:
        while sup.is_running:
            time.sleep(1.0)
            stats = sup.stats()
            cam = stats.get("camera-webcam")
            if cam is not None and cam.fps == 0 and cam.processed == 0:
                logger.warning("No frames yet — is a camera connected?")
    except KeyboardInterrupt:
        pass
    finally:
        sup.stop()


if __name__ == "__main__":
    main()
