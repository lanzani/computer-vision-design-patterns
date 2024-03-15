# -*- coding: utf-8 -*-
import time
from abc import ABC, abstractmethod

from transitions import Machine, State


class Counter(ABC, Machine):
    inactive = State(name="inactive")
    active = State(name="active")

    states = [inactive, active]
    transitions = [
        {"trigger": "activate", "source": inactive, "dest": active},
        {"trigger": "deactivate", "source": "*", "dest": inactive},
    ]

    def __init__(self):
        Machine.__init__(self, states=Counter.states,
                         transitions=Counter.transitions,
                         initial=Counter.inactive)

    @abstractmethod
    def reset(self):
        pass

    @abstractmethod
    def update(self):
        pass


class ManualCounter(Counter):

    def __init__(self, threshold: int):
        super().__init__()
        self._counter = 0
        self._threshold = threshold

    def reset(self):
        self._counter = 0
        self.deactivate()

    def update(self):
        self._counter += 1

        if self._counter == self._threshold:
            self.activate()
