# -*- coding: utf-8 -*-
"""StageRunner — owns the worker loop, error policy, pacing, and metrics.

The actual loop lives in ``_StageWorker``, a self-contained, picklable payload
that can run in a thread or be spawned into a child process. It holds no
references to the Supervisor, so PROCESS stages work with the spawn start
method (required on Windows). Metrics travel back over a shared
multiprocessing queue (the "control bus") instead of callbacks.
"""

from __future__ import annotations

import multiprocessing as mp
import os
import queue
import threading
import time
from dataclasses import replace

from loguru import logger

from computer_vision_design_patterns.pipeline_v3.channel import Channel, ChannelClosed
from computer_vision_design_patterns.pipeline_v3.packet import SENTINEL, Packet
from computer_vision_design_patterns.pipeline_v3.stage import (
    ExecutorType,
    SourceStage,
    Stage,
    StageMetrics,
    StopStage,
)

IDLE_WAIT_S = 0.005
"""Stop-aware wait when a non-source stage has no input this tick."""

METRICS_INTERVAL_S = 0.25
"""How often metrics/heartbeat snapshots are pushed to the control bus."""


class _StageWorker:
    """Picklable worker payload. Runs the stage loop in a thread or child process."""

    def __init__(
        self,
        stage: Stage,
        input_channels: dict[str, Channel],
        output_channels: dict[str, list[Channel]],
        stop_event,
        ready_event,
        metrics_queue=None,
    ):
        self.stage = stage
        self.input_channels = input_channels
        self.output_channels = output_channels
        self.stop_event = stop_event
        self.ready_event = ready_event
        self.metrics_queue = metrics_queue

        self._is_source = isinstance(stage, SourceStage) or not input_channels
        self._metrics = StageMetrics(stage_name=stage.name)
        self._fps_ticks: list[float] = []
        self._last_push = 0.0

    # -- main loop ------------------------------------------------------------

    def run(self) -> None:
        logger.info(f"Stage {self.stage.name!r} starting (pid={os.getpid()})")
        try:
            self.stage.setup()
        except Exception:
            logger.exception(f"setup() failed for stage {self.stage.name!r}")
            self._metrics.healthy = False
            self._push_metrics(force=True)
            return

        self.ready_event.set()
        self._push_metrics(force=True)
        logger.info(f"Stage {self.stage.name!r} ready")

        try:
            self._loop()
        finally:
            try:
                self.stage.teardown()
            except Exception:
                logger.exception(f"teardown() failed for stage {self.stage.name!r}")
            for channel in list(self.input_channels.values()):
                channel.release_consumer_resources()
            for channels in self.output_channels.values():
                for channel in channels:
                    channel.release_producer_resources()
            self._push_metrics(force=True)
            logger.info(f"Stage {self.stage.name!r} stopped")

    def _loop(self) -> None:
        policy = self.stage.error_policy
        consecutive_failures = 0
        error_backoff = policy.initial_backoff_s

        # Source pacing (sources never sleep themselves; the loop paces them).
        read_backoff_min = getattr(self.stage, "read_backoff_s", 0.05)
        read_backoff_max = getattr(self.stage, "max_read_backoff_s", 2.0)
        read_backoff = read_backoff_min
        target_fps = getattr(self.stage, "target_fps", None)
        frame_period = (1.0 / target_fps) if target_fps else None

        while not self.stop_event.is_set():
            tick_start = time.perf_counter()
            try:
                worked = self._tick()
            except StopStage:
                logger.info(f"Stage {self.stage.name!r} requested graceful stop")
                self.stop_event.set()
                return
            except Exception:
                consecutive_failures += 1
                self._metrics.errors += 1
                self._metrics.healthy = False
                logger.exception(f"Error in stage {self.stage.name!r} ({consecutive_failures} consecutive)")
                self._push_metrics(force=True)
                if consecutive_failures >= policy.max_consecutive_failures:
                    logger.error(
                        f"Stage {self.stage.name!r} exceeded "
                        f"{policy.max_consecutive_failures} consecutive failures — worker exiting"
                    )
                    # Exit WITHOUT setting stop_event: the supervisor sees an
                    # unexpected death and applies the restart policy.
                    return
                self.stop_event.wait(error_backoff)
                error_backoff = min(error_backoff * policy.backoff_factor, policy.max_backoff_s)
                continue

            consecutive_failures = 0
            error_backoff = policy.initial_backoff_s
            self._metrics.healthy = True
            self._push_metrics()

            if not worked:
                if self._is_source:
                    # Source produced nothing (camera down, EOF, …): back off.
                    self.stop_event.wait(read_backoff)
                    read_backoff = min(read_backoff * 2.0, read_backoff_max)
                else:
                    self.stop_event.wait(IDLE_WAIT_S)
                continue

            read_backoff = read_backoff_min
            if frame_period is not None:
                elapsed = time.perf_counter() - tick_start
                if elapsed < frame_period:
                    self.stop_event.wait(frame_period - elapsed)

    # -- one tick ---------------------------------------------------------------

    def _tick(self) -> bool:
        """Run one tick. Returns True if the stage did work, False if idle."""
        if self._is_source:
            started = time.perf_counter()
            outputs = self.stage.process({})
            if not outputs:
                return False
            self._record(started)
            self._emit(outputs)
            return True

        inputs = self._sweep()
        if not inputs:
            return False

        started = time.perf_counter()
        outputs = self.stage.process(inputs)
        self._record(started)
        if outputs:
            self._emit(outputs)
        return True

    def _sweep(self) -> dict[str, Packet]:
        """Non-blocking sweep over all input channels (at most one packet each).

        Latency does not scale with the number of idle ports. A SENTINEL means
        that edge closed: the port is dropped and ``on_port_closed`` fires; the
        stage itself keeps running (fan-in stages survive stream removal).
        """
        got: dict[str, Packet] = {}
        for name, channel in list(self.input_channels.items()):
            try:
                item = channel.get_nowait()
            except (queue.Empty, ValueError, OSError):
                continue

            if item is SENTINEL:
                self.input_channels.pop(name, None)
                try:
                    self.stage.on_port_closed(name)
                except Exception:
                    logger.exception(f"on_port_closed({name!r}) failed in {self.stage.name!r}")
                continue

            got[name] = item
        return got

    def _emit(self, outputs: dict[str, Packet | None]) -> None:
        for port_name, packet in outputs.items():
            if packet is None:
                continue
            for channel in list(self.output_channels.get(port_name, [])):
                try:
                    channel.put(packet)
                except ChannelClosed:
                    # Downstream detached — stop sending to this channel.
                    remaining = self.output_channels.get(port_name, [])
                    self.output_channels[port_name] = [c for c in remaining if c is not channel]
                except Exception:
                    logger.exception(f"Failed to put on output {port_name!r} of stage {self.stage.name!r}")

    # -- metrics ------------------------------------------------------------------

    def _record(self, started: float) -> None:
        now = time.time()
        self._metrics.processed += 1
        self._metrics.last_latency_ms = (time.perf_counter() - started) * 1000.0
        self._fps_ticks = [t for t in self._fps_ticks if t >= now - 1.0]
        self._fps_ticks.append(now)
        self._metrics.fps = float(len(self._fps_ticks))

    def _push_metrics(self, force: bool = False) -> None:
        if self.metrics_queue is None:
            return
        now = time.time()
        if not force and now - self._last_push < METRICS_INTERVAL_S:
            return
        self._last_push = now
        self._metrics.pid = os.getpid()
        self._metrics.last_heartbeat = now
        self._metrics.drops = sum(channel.drops for channels in self.output_channels.values() for channel in channels)
        try:
            self.metrics_queue.put_nowait(replace(self._metrics))
        except Exception:
            pass  # bus full or closing — heartbeats are best-effort


class StageRunner:
    """Parent-side handle for a stage worker (thread or process)."""

    def __init__(
        self,
        stage: Stage,
        input_channels: dict[str, Channel] | None = None,
        output_channels: dict[str, list[Channel]] | None = None,
        metrics_queue=None,
        join_timeout: float = 5.0,
        ctx: mp.context.BaseContext | None = None,
    ):
        self.stage = stage
        self.join_timeout = join_timeout
        ctx = ctx or mp.get_context("spawn")

        is_thread = stage.executor == ExecutorType.THREAD
        self._stop = threading.Event() if is_thread else ctx.Event()
        self._ready = threading.Event() if is_thread else ctx.Event()

        self._payload = _StageWorker(
            stage=stage,
            input_channels=input_channels if input_channels is not None else {},
            output_channels=output_channels if output_channels is not None else {},
            stop_event=self._stop,
            ready_event=self._ready,
            metrics_queue=metrics_queue,
        )

        worker_cls = threading.Thread if is_thread else ctx.Process
        self._worker = worker_cls(target=self._payload.run, name=f"stage-{stage.name}", daemon=True)

    # -- dynamic wiring (THREAD stages only — shared memory with the worker) ----

    @property
    def input_channels(self) -> dict[str, Channel]:
        return self._payload.input_channels

    @property
    def output_channels(self) -> dict[str, list[Channel]]:
        return self._payload.output_channels

    def add_input_channel(self, port_name: str, channel: Channel) -> None:
        self._ensure_attachable()
        self._payload.input_channels[port_name] = channel

    def add_output_channel(self, port_name: str, channel: Channel) -> None:
        self._ensure_attachable()
        self._payload.output_channels.setdefault(port_name, []).append(channel)

    def _ensure_attachable(self) -> None:
        if self.stage.executor == ExecutorType.PROCESS and self.is_alive():
            raise RuntimeError(f"Cannot hot-attach channels to running PROCESS stage {self.stage.name!r}")

    # -- lifecycle ---------------------------------------------------------------

    def is_alive(self) -> bool:
        return self._worker.is_alive()

    @property
    def stop_requested(self) -> bool:
        """True if this runner was told to stop (or stopped itself gracefully)."""
        return self._stop.is_set()

    def start(self) -> None:
        self._worker.start()

    def wait_ready(self, timeout: float | None = 10.0) -> bool:
        return self._ready.wait(timeout=timeout)

    def stop(self) -> None:
        self._stop.set()

    def join(self, timeout: float | None = None) -> None:
        if timeout is None:
            timeout = self.join_timeout
        self._worker.join(timeout=timeout)
        if not self._worker.is_alive():
            return

        logger.warning(f"Stage {self.stage.name!r} did not stop in {timeout}s — forcing")
        if isinstance(self._worker, mp.process.BaseProcess):
            self._worker.terminate()
            self._worker.join(timeout=2.0)
            if self._worker.is_alive():
                self._worker.kill()
                self._worker.join(timeout=1.0)
        # Threads cannot be force-killed; the daemon flag prevents hangs at exit.
