# Computer Vision Design Patterns

[![Copier](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/copier-org/copier/master/img/badge/badge-grayscale-border.json)](https://github.com/copier-org/copier)
[![uv](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/uv/main/assets/badge/v0.json)](https://github.com/astral-sh/uv)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)

[![GitHub Release](/reports/version-badge.svg?dummy=8484754)]()
[![Coverage Status](/reports/coverage-badge.svg?dummy=8484744)](./reports/coverage/index.html)

## Technology stack

- [uv](https://docs.astral.sh/uv/) for python and project manager
- [pre-commit](https://pre-commit.com/) with [ruff](https://docs.astral.sh/ruff/) to mantain code consistency and pre-commit checks
- [GitHub Actions](https://github.com/features/actions) to create release and publish package (also on a private registry)

## Installation

**Note**: You need [uv](https://docs.astral.sh/uv/) (and uv only) installed on your machine.

To install the package:

```bash
uv sync
```

# Usage

## Events

### TimeEvent

TimeEvent activates immediately when triggered and automatically deactivates after a specified duration.

```python
from computer_vision_design_patterns.event import TimeEvent
import time

# Create an event that stays active for 2 seconds
event = TimeEvent(2)

# Trigger the event
event.trigger()
print(event.is_active())  # True

# After 2 seconds
time.sleep(2)
print(event.is_active())  # False

# Retriggering resets the timer
event.trigger()
print(event.is_active())  # True again
```

### CountdownEvent

CountdownEvent starts inactive, counts down for a specified duration, and then activates.

```python
from computer_vision_design_patterns.event import CountdownEvent
import time

# Create a countdown event for 3 seconds
event = CountdownEvent(3)

# Start the countdown
event.trigger()
print(event.is_active())  # False (still counting down)

# After 3 seconds
time.sleep(3)
print(event.is_active())  # True (countdown completed)

# Reset the event
event.reset()
print(event.is_active())  # False
```

### Key Differences

1. **TimeEvent**:

   - Activates immediately upon trigger and can be triggered multiple times
   - Automatically deactivates after the duration has elapsed
   - Can be reset by triggering again

2. **CountdownEvent**:
   - Starts inactive
   - Can be triggered multiple times
   - Activates only after countdown completes
   - Stays active until manually reset

### Examples

Check the `dev` folder for comprehensive examples of both event types.

## Counters

### ManualCounter

ManualCounter is a simple counter that activates when it reaches a specified threshold value. It requires manual updates and can be reset to start counting again.

```python
from computer_vision_design_patterns.counter import ManualCounter
import time

# Create a counter that activates after 3 counts
counter = ManualCounter(3)

# Update the counter
counter.update()
print(counter.is_active())  # False (count = 1)

counter.update()
print(counter.is_active())  # False (count = 2)

counter.update()
print(counter.is_active())  # True (count = 3)

# Reset the counter
counter.reset()
print(counter.is_active())  # False (count = 0)
```

## Pipeline

The Pipeline pattern provides a framework for building real-time image processing pipelines. It consists of three core concepts:

1. **Payload**: Immutable data units that flow through the pipeline (e.g., image frames, detection results)
2. **Stage**: Computation units that process payloads (e.g., filters, transformations, analyzers)
3. **Pipeline**: Orchestrator that manages stages and their connections

### Core Concepts

#### Payload

Payloads are immutable data containers that carry information between stages. They are implemented as frozen dataclasses to ensure data integrity.

```python
from dataclasses import dataclass, field
from computer_vision_design_patterns.pipeline import Payload
import numpy as np

@dataclass(frozen=True, eq=False, slots=True)
class ImagePayload(Payload):
    frame: np.ndarray
    metadata: dict = field(default_factory=dict)
```

#### Stage

Stages are processing units that transform payloads. Each stage runs in its own thread or process and communicates with other stages via queues.

**Stage Types:**
- `One2One`: Single input → single output (e.g., image filter)
- `One2Many`: Single input → multiple outputs (e.g., stream duplication)
- `Many2One`: Multiple inputs → single output (e.g., stream merging)
- `Many2Many`: Multiple inputs → multiple outputs (e.g., complex routing)

**Stage Executors:**
- `THREAD`: Runs in a separate thread (good for I/O-bound tasks)
- `PROCESS`: Runs in a separate process (good for CPU-intensive tasks)

```python
from computer_vision_design_patterns.pipeline import Payload, Stage
from computer_vision_design_patterns.pipeline.stage import StageExecutor, StageType
import cv2

class GrayscaleStage(Stage):
    def __init__(self, stage_executor: StageExecutor):
        super().__init__(
            stage_type=StageType.One2One,
            stage_executor=stage_executor
        )

    def pre_run(self):
        # Initialize resources (models, connections, etc.)
        pass

    def process(self, key: str, payload: Payload | None) -> Payload | None:
        if payload is None:
            return None

        # Process the payload
        gray_frame = cv2.cvtColor(payload.frame, cv2.COLOR_BGR2GRAY)
        return ImagePayload(frame=gray_frame, timestamp=payload.timestamp)

    def post_run(self):
        # Cleanup resources
        pass
```

#### Pipeline

The Pipeline orchestrates stages and manages their lifecycle.

```python
from computer_vision_design_patterns.pipeline import Pipeline
from computer_vision_design_patterns.pipeline.stage import StageExecutor

# Create pipeline
pipeline = Pipeline()

# Create stages
source = VideoSourceStage(camera_id=0, executor=StageExecutor.PROCESS)
processor = GrayscaleStage(executor=StageExecutor.THREAD)
sink = DisplayStage(executor=StageExecutor.PROCESS)

# Add stages
pipeline.add_stage(source)
pipeline.add_stage(processor)
pipeline.add_stage(sink)

# Connect stages
pipeline.link_stages(source, processor, "stream1")
pipeline.link_stages(processor, sink, "stream1")

# Start processing
pipeline.start()

try:
    # Pipeline runs until interrupted
    time.sleep(60)
finally:
    # Clean shutdown
    pipeline.stop_all_stages()
```

### Advanced Usage

#### Multi-Stream Pipeline

Handle multiple data streams in a single pipeline:

```python
# Create multiple sources
stream1 = VideoSourceStage(0, StageExecutor.PROCESS)
stream2 = VideoSourceStage(1, StageExecutor.PROCESS)

# Shared processor
processor = GrayscaleStage(StageExecutor.THREAD)

# Multiple sinks
sink1 = DisplayStage(StageExecutor.PROCESS)
sink2 = DisplayStage(StageExecutor.PROCESS)

# Link streams
pipeline.link_stages(stream1, processor, "stream1")
pipeline.link_stages(stream2, processor, "stream2")
pipeline.link_stages(processor, sink1, "stream1")
pipeline.link_stages(processor, sink2, "stream2")
```

#### Dynamic Stream Management

Add or remove streams at runtime:

```python
# Start pipeline
pipeline.start()

# Process for a while
time.sleep(10)

# Remove a stream
pipeline.unlink("stream1")

# Continue with remaining streams
time.sleep(10)

# Stop all
pipeline.stop_all_stages()
```

#### Backpressure Handling

Configure queue sizes to handle backpressure:

```python
# Stage with bounded output queue
stage = MyStage(
    stage_executor=StageExecutor.PROCESS,
    output_maxsize=10,  # Max 10 items in queue
    queue_timeout=0.1   # 100ms timeout for operations
)
```

When queues are full, the oldest items are automatically dropped to maintain real-time performance.

### Design Benefits

1. **Modularity**: Each stage is independent and can be developed/tested separately
2. **Scalability**: Use PROCESS executor for CPU-bound stages to utilize multiple cores
3. **Flexibility**: Support for complex topologies (fan-in, fan-out, routing)
4. **Real-time**: Queue-based communication with backpressure handling
5. **Type Safety**: Immutable payloads prevent accidental data corruption
6. **Graceful Shutdown**: Poison pill pattern for clean termination

### Examples

Check the `dev/dev_pipeline.py` file for a comprehensive example demonstrating:
- Multiple video streams
- Shared processing stages
- Stream duplication and routing
- Dynamic stream management

## Examples

Check the `dev/` folder for comprehensive examples of counter usage.

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

This project is licensed under the MIT License - see the LICENSE file for details.
