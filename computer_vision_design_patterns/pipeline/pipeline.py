# -*- coding: utf-8 -*-
import time
from typing import List
import multiprocessing as mp

from loguru import logger

from computer_vision_design_patterns.pipeline.stage import Stage, StageExecutor


class Pipeline:
    def __init__(self):
        self.stages: List[Stage] = []
        self.manager = mp.Manager()

    def add_stage(self, stage: Stage):
        self.stages.append(stage)

    def link_stages(self, from_stage: Stage, to_stage: Stage, key: str):
        maxsize = 0 if from_stage.output_maxsize is None else from_stage.output_maxsize
        queue = self.manager.Queue(maxsize=maxsize)
        from_stage.link(to_stage, key, queue)

    def start(self):
        for stage in self.stages:
            try:
                if not stage.is_alive():
                    stage.start()
            except RuntimeError as e:
                logger.warning(e)

    def stop(self):
        logger.info("Stopping pipeline")
        # Set stop flag for all stages
        for stage in self.stages:
            stage.set_stop_flag()

        # Wait for all stages to stop
        max_wait_time = 10  # Maximum wait time in seconds
        start_time = time.time()

        while (time.time() - start_time) < max_wait_time:
            alive_stages = [stage for stage in self.stages if stage.is_alive()]
            if not alive_stages:
                logger.info("All stages have stopped")
                break

            logger.info(
                f"Waiting for {len(alive_stages)} stages to stop: {[stage.__class__.__name__ for stage in alive_stages]}"
            )
            time.sleep(1)

        # Force stop any remaining stages
        for stage in self.stages:
            if stage.is_alive():
                logger.warning(f"Force stopping {stage.__class__.__name__}")
                stage.force_stop()

        # Now join all stages
        for stage in self.stages:
            stage.join()

        logger.info("Pipeline stopped")

    def flush(self):
        self.stop()
        self.stages = []
