# -*- coding: utf-8 -*-
from computer_vision_design_patterns.pipeline.stage import Stage, PoisonPill


class Pipeline:
    def __init__(self):
        self.stages: list[Stage] = []

    def add_stage(self, stage: Stage):
        self.stages.append(stage)

    @staticmethod
    def link_stages(from_stage: Stage, to_stage: Stage, key: str):
        from_stage.link(to_stage, key)

    def unlink(self, key: str):
        for stage in self.stages:
            stage.unlink(key)

        # Remove not alive stages
        self.stages = [stage for stage in self.stages if stage.is_alive()]

    def start(self):
        for stage in self.stages:
            if not stage.is_alive():
                stage.start()

    def stop(self):
        for stage in reversed(self.stages):
            stage.stop()

        for stage in reversed(self.stages):
            stage.join()

    def stop_all_stages(self):
        for stage in self.stages:
            for queue in stage._output_queues.values():
                queue.put(PoisonPill())
            stage.stop()
            stage.join()

    # def chain_poison_pill(self, source_stage_type):
    #     for stage in self.stages:
    #         if isinstance(stage, source_stage_type):
    #             stage.poison_pill()
    #
    #     for stage in self.stages:
    #         stage.join()

    def flush(self):
        self.stages = []
