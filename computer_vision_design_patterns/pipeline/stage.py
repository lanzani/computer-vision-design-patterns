# -*- coding: utf-8 -*-
from __future__ import annotations

from abc import abstractmethod, ABC
import multiprocessing as mp

import threading

from computer_vision_design_patterns.pipeline import Payload


class Stage(ABC):
    key: str
    output_maxsize: int | None
    queue_timeout: int | None
    control_queue: mp.Queue | None

    @abstractmethod
    def get_from_left(self) -> Payload | dict[str, Payload] | None:
        pass

    @abstractmethod
    def put_to_right(self, payload: Payload | dict[str, Payload]) -> None:
        pass

    @abstractmethod
    def link(self, stage: Stage) -> None:
        pass

    @abstractmethod
    def process(self, payload: Payload | None):
        pass

    @abstractmethod
    def run(self) -> None:
        pass


class ProcessStage(mp.Process):
    def __init__(self, name: str | None = None):
        super().__init__(name=self.__class__.__name__ if name is None else name)
        self.stop_event = mp.Event()

    def terminate(self):
        self.stop_event.set()


class ThreadStage(threading.Thread):
    def __init__(self, name: str | None = None):
        super().__init__(name=self.__class__.__name__ if name is None else name)
        self.stop_event = threading.Event()

    def terminate(self):
        self.stop_event.set()
