# -*- coding: utf-8 -*-
from computer_vision_design_patterns.pipeline.stage import Stage


class Pipeline:
    def __init__(self):
        self.stages: list[Stage] = []

    def add_stage(self, stage: Stage):
        self.stages.append(stage)

    @staticmethod
    def link_stages(from_stage: Stage, to_stage: Stage, key: str):
        from_stage.link(to_stage, key)

    def unlink_data_source(self, key: str):
        for stage in self.stages:
            stage.unlink(key)

    def start(self):
        for stage in self.stages:
            if not stage.is_alive():
                stage.start()

    def stop(self):
        for stage in self.stages:
            stage.stop()

    def flush(self):
        self.stages = []
