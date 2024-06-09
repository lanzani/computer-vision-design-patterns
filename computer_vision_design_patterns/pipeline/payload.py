# -*- coding: utf-8 -*-
from dataclasses import dataclass


@dataclass(frozen=True, eq=False, slots=True)
class Payload:
    """
    Payload class that will be used to pass data between stages.

    'frozen=True' makes the payload immutable, so it can't be changed by mistake after its creation.
    """

    timestamp: float
