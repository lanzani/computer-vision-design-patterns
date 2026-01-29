# -*- coding: utf-8 -*-
from abc import ABC, abstractmethod

from transitions import Machine, State


class Counter(ABC, Machine):
    """Base class for counter implementations with state management.

    This abstract class implements a simple state machine with two states:
    'active' and 'inactive'. Counters can transition between these states
    based on their specific counting logic.

    States:
        - inactive: Default initial state
        - active: Activated state when counter conditions are met
    """

    inactive = State(name="inactive")
    active = State(name="active")

    states = [inactive, active]
    transitions = [
        {"trigger": "activate", "source": inactive, "dest": active},
        {"trigger": "deactivate", "source": "*", "dest": inactive},
    ]

    def __init__(self):
        Machine.__init__(self, states=Counter.states, transitions=Counter.transitions, initial=Counter.inactive)

    @abstractmethod
    def reset(self):
        pass

    @abstractmethod
    def update(self):
        pass


# Manual counter 1
class ManualCounter(Counter):
    """A counter that activates when it reaches a specified threshold.

    This counter increments manually through update() calls and activates
    when the count equals the threshold value. It can be reset to start
    counting again from zero.

    Args:
        threshold (int): The count value at which the counter will activate

    Example:
        ```python
        # Create a counter that activates after 3 counts
        counter = ManualCounter(3)

        # Update counter multiple times
        counter.update()  # count = 1, active = False
        counter.update()  # count = 2, active = False
        counter.update()  # count = 3, active = True

        # Check if counter is active
        print(counter.is_active())  # True

        # Reset the counter
        counter.reset()  # count = 0, active = False
        ```
    """

    def __init__(self, threshold: int):
        super().__init__()
        self.counter = 0
        self.threshold = threshold

    def reset(self):
        """Resets the counter to zero and deactivates it."""
        self.counter = 0
        self.deactivate()

    def update(self):
        """Increments the counter and activates it if threshold is reached."""
        self.counter += 1
        if self.counter == self.threshold:
            self.activate()

    def is_active(self) -> bool:
        """Checks if the counter has reached its threshold.

        Returns:
            bool: True if counter has reached threshold, False otherwise.
        """
        return self.state == self.active.name
