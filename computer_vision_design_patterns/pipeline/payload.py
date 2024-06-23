# -*- coding: utf-8 -*-
import time
from dataclasses import dataclass, field


@dataclass(frozen=True, eq=False, slots=True)
class Payload:
    """
    Payload class that will be used to pass data between stages.

    'frozen=True' makes the payload immutable, so it can't be changed by mistake after its creation.
    'eq=False' disables the default equality check, which is not needed for this class.
    'slots=True' reduces memory usage and access time by not creating a __dict__ attribute for each instance.
    """

    timestamp: float = field(default_factory=time.time)
