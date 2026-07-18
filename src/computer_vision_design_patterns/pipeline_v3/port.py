# -*- coding: utf-8 -*-
"""Typed input/output ports for stages."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Type

from computer_vision_design_patterns.pipeline_v3.packet import Packet

if TYPE_CHECKING:
    from computer_vision_design_patterns.pipeline_v3.stage import Stage


@dataclass(slots=True)
class Port:
    """Named, typed connection point on a stage.

    Fan-out and fan-in are properties of the wiring graph, not of the stage
    class itself. A port is identified by ``(stage, name)``.
    """

    stage: Stage
    name: str
    packet_type: Type[Packet]
    direction: str  # "in" | "out"

    def __repr__(self) -> str:
        stage_name = getattr(self.stage, "name", type(self.stage).__name__)
        return f"Port({stage_name}.{self.name}:{self.direction})"

    def __hash__(self) -> int:
        return hash((id(self.stage), self.name, self.direction))

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Port):
            return NotImplemented
        return self.stage is other.stage and self.name == other.name and self.direction == other.direction
