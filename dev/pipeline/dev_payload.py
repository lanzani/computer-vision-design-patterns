# -*- coding: utf-8 -*-
from dataclasses import dataclass

import numpy as np

from computer_vision_design_patterns.pipeline.payload import Payload


@dataclass(frozen=True, eq=False, slots=True)
class ImagePayload(Payload):
    frame: np.ndarray | None = None


def main():
    image_payload = ImagePayload(frame=np.array([[1, 2, 3], [4, 5, 6], [7, 8, 9]]))
    print(image_payload.timestamp)


if __name__ == "__main__":
    main()
