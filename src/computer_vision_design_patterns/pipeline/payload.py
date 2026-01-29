# -*- coding: utf-8 -*-
import time
from dataclasses import dataclass, field


@dataclass(frozen=True, eq=False, slots=True)
class Payload:
    """
    Base class for data units passed between pipeline stages.

    The Payload is the fundamental data unit in the pipeline architecture. It represents
    a single piece of data (e.g., an image frame, detection results) that flows through
    the processing stages.

    Attributes:
        timestamp: Creation timestamp of the payload, automatically set to current time.

    Design Decisions:
        - frozen=True: Makes the payload immutable, preventing accidental modification
          after creation. This ensures data integrity as payloads pass through multiple stages.
        - eq=False: Disables default equality checks, as payloads are unique data units
          and equality comparison is typically not needed.
        - slots=True: Reduces memory usage and improves access speed by avoiding
          per-instance __dict__ creation. Important for high-throughput real-time processing.

    Example:
        Create a custom payload for image data:

        ```python
        @dataclass(frozen=True, eq=False, slots=True)
        class ImagePayload(Payload):
            frame: np.ndarray
        ```

    Note:
        All payloads should inherit from this base class and maintain immutability.
        To pass modified data, create a new payload instance rather than mutating existing ones.
    """

    timestamp: float = field(default_factory=time.time)
