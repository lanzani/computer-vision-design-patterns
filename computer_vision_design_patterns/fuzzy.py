# -*- coding: utf-8 -*-
from typing import Callable


class ConditionalBoolean:
    def __init__(self, expression: Callable):
        self._expression = expression

    def eval(self, *args) -> bool:
        return self._expression(*args)
