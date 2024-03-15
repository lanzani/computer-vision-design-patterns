# -*- coding: utf-8 -*-
import time
from abc import ABC, abstractmethod

from transitions import Machine, State

# Auto deactivating Event

# Manual deactivating Event


class Event(ABC, Machine):
    inactive = State(name="inactive")
    active = State(name="active")

    states = [inactive, active]
    transitions = [
        {"trigger": "activate", "source": inactive, "dest": active},
        {"trigger": "deactivate", "source": "*", "dest": inactive},
    ]

    def __init__(self):
        Machine.__init__(self, states=Event.states,
                         transitions=Event.transitions,
                         initial=Event.inactive)


class TimeEvent(Event):

    def __init__(self, event_seconds_duration: float):
        super().__init__()
        self._event_seconds_duration = event_seconds_duration
        self._last_call_time = None

    def trigger(self):
        self._last_call_time = time.time()
        self.activate()

    def update_state(self):
        if self._last_call_time is not None:
            if time.time() - self._last_call_time > self._event_seconds_duration:
                self.deactivate()
                self._last_call_time = None
