# -*- coding: utf-8 -*-
"""OpenCV display sink."""

from __future__ import annotations

from computer_vision_design_patterns.pipeline_v3.packet import FramePacket, Packet
from computer_vision_design_patterns.pipeline_v3.stage import ExecutorType, SinkStage, StopStage


class VideoSink(SinkStage):
    """Display frames with OpenCV.

    Accepts any packet with a ``frame`` attribute (FramePacket, PosePacket).
    Pressing the quit key raises ``StopStage``, which stops this stage
    gracefully (windows are destroyed in ``teardown``); the supervisor treats
    it as intentional and does not restart the sink.
    """

    def __init__(
        self,
        name: str = "video-sink",
        executor: ExecutorType = ExecutorType.THREAD,
        quit_key: str = "q",
    ):
        super().__init__(name=name, executor=executor)
        self.quit_key = quit_key
        self.frames_in = self.add_input("frames", FramePacket)

    def teardown(self) -> None:
        try:
            import cv2

            cv2.destroyAllWindows()
        except Exception:
            pass

    def consume(self, port_name: str, packet: Packet) -> None:
        frame = getattr(packet, "frame", None)
        if frame is None:
            return

        import cv2

        cv2.imshow(f"VideoSink:{packet.stream_id}", frame)
        key = cv2.waitKey(1) & 0xFF
        if key == ord(self.quit_key):
            raise StopStage(f"quit key {self.quit_key!r} pressed")
