# -*- coding: utf-8 -*-
import time
from abc import ABC

from transitions import Machine, State


# Auto deactivating Event

# Manual deactivating Event


class Event(ABC, Machine):
    inactive = State(name="inactive")
    active = State(name="active")

    states = [inactive, active]
    transitions = [
        {"trigger": "activate", "source": "*", "dest": active},
        {"trigger": "deactivate", "source": "*", "dest": inactive},
    ]

    def __init__(self):
        Machine.__init__(self, states=Event.states, transitions=Event.transitions, initial=Event.inactive)


class TimeEvent(Event):
    def __init__(self, event_seconds_duration: float):
        super().__init__()
        self._event_seconds_duration = event_seconds_duration
        self._last_call_time = None

    def trigger(self):
        self._last_call_time = time.time()
        self.activate()

    def _update_timer(self):
        if self._last_call_time is not None:
            if time.time() - self._last_call_time > self._event_seconds_duration:
                self.deactivate()
                self._last_call_time = None

    def is_active(self) -> bool:
        self._update_timer()
        return self.state == self.active.name


class CountdownEvent(Event):
    def __init__(self, countdown_duration: float):
        super().__init__()
        self._countdown_duration = countdown_duration
        self._last_call_time = None

    def trigger(self):
        if self._last_call_time is None:
            self._last_call_time = time.time()

    def _update_timer(self):
        if self._last_call_time is not None:
            if time.time() - self._last_call_time > self._countdown_duration:
                self.activate()

    def is_active(self) -> bool:
        self._update_timer()
        return self.state == self.active.name

    def reset(self):
        self._last_call_time = None
        self.deactivate()
