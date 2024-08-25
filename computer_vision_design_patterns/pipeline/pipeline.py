# -*- coding: utf-8 -*-
from venv import logger
import multiprocessing as mp

from computer_vision_design_patterns.pipeline.sample_stage import SimpleStreamStage
from computer_vision_design_patterns.pipeline.stage import Stage, PoisonPill


class Pipeline:
    def __init__(self):
        self.stages: list[Stage] = []
        self.manager = mp.Manager()

    def add_stage(self, stage: Stage):
        self.stages.append(stage)

    def link_stages(self, from_stage: Stage, to_stage: Stage, key: str):
        maxsize = from_stage._output_maxsize if from_stage._output_maxsize is not None else 0

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
        for stage in self.stages:
            stage.stop()

        for stage in self.stages:
            stage.join()

    def unlink(self, key: str):
        pass

    def flush(self):
        self.stop()
        self.stages = []
