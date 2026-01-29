# -*- coding: utf-8 -*-
import threading
import time
from abc import ABC

from transitions import Machine, State


class Event(ABC, Machine):
    """Base class for event handling with state management.

    This abstract class implements a simple state machine with two states:
    'active' and 'inactive'. It provides basic state transition functionality.

    States:
        - inactive: Default initial state
        - active: Activated state

    Transitions:
        - activate: Transitions to active state from any state
        - deactivate: Transitions to inactive state from any state
    """

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
    """An event that automatically deactivates after a specified duration.

    This event type activates immediately when triggered and automatically
    deactivates after the specified duration has elapsed. It is thread-safe
    and can be used in concurrent applications.

    Args:
        event_seconds_duration (float): Duration in seconds before the event
            automatically deactivates.

    Example:
        ```python
        # Create an event that stays active for 5 seconds
        timer_event = TimeEvent(5.0)

        # Trigger the event
        timer_event.trigger()

        # Check if event is still active
        if timer_event.is_active():
            print("Event is active")

        # After 5 seconds
        time.sleep(5)
        print("Event active:", timer_event.is_active())  # Will print False
        ```
    """

    def __init__(self, event_seconds_duration: float):
        super().__init__()
        self._event_seconds_duration = event_seconds_duration
        self._last_call_time = None
        self._lock = threading.Lock()

    def trigger(self) -> None:
        """Activates the event and starts the timer.

        The timer can be reset to the initial value by calling trigger() again.
        """
        with self._lock:
            self._last_call_time = time.time()
            self.activate()

    def _update_timer(self):
        with self._lock:
            if self._last_call_time is not None:
                if time.time() - self._last_call_time > self._event_seconds_duration:
                    self.deactivate()
                    self._last_call_time = None

    def is_active(self) -> bool:
        """Checks if the event is currently active.

        Returns:
            bool: True if the timer is active (the timer is still running), False otherwise.
        """
        self._update_timer()
        with self._lock:
            return self.state == self.active.name


class CountdownEvent(Event):
    """An event that activates after a specified countdown duration.

    Unlike TimeEvent, this event starts inactive and begins counting down
    when triggered. Once the countdown completes, the event activates and
    stays active until manually reset.

    Args:
        countdown_duration (float): Duration in seconds to wait before
            activating the event.

    Example:
        ```python
        # Create a countdown event for 3 seconds
        countdown = CountdownEvent(3.0)

        # Start the countdown
        countdown.trigger()

        # Check status immediately
        print("Active:", countdown.is_active())  # Will print False

        # After 3 seconds
        time.sleep(3)
        print("Active:", countdown.is_active())  # Will print True

        # Reset the countdown
        countdown.reset()
        print("Active:", countdown.is_active())  # Will print False
        ```
    """

    def __init__(self, countdown_duration: float):
        super().__init__()
        self._countdown_duration = countdown_duration
        self._last_call_time = None

    def trigger(self):
        """Starts the countdown timer if not already running.

        The event will activate after the countdown_duration has elapsed
        from the first trigger call.
        """
        if self._last_call_time is None:
            self._last_call_time = time.time()

    def _update_timer(self):
        if self._last_call_time is not None:
            if time.time() - self._last_call_time > self._countdown_duration:
                self.activate()

    def is_active(self) -> bool:
        """Checks if the countdown has completed and the event is active.

        Returns:
            bool: True if the countdown has completed and event is active,
                False otherwise.
        """
        self._update_timer()
        return self.state == self.active.name

    def reset(self):
        """Resets the countdown timer and deactivates the event.

        Can be used to start a fresh countdown by calling trigger() again.
        """
        self._last_call_time = None
        self.deactivate()
