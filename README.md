# Computer Vision Design Patterns

[![Copier](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/copier-org/copier/master/img/badge/badge-grayscale-border.json)](https://github.com/copier-org/copier)
[![uv](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/uv/main/assets/badge/v0.json)](https://github.com/astral-sh/uv)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)

[![GitHub Release](/reports/version-badge.svg?dummy=8484754)]()
[![Coverage Status](/reports/coverage-badge.svg?dummy=8484744)](./reports/coverage/index.html)

## Tecnology stack

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

## Examples

Check the `dev/` folder for comprehensive examples of counter usage.

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

This project is licensed under the MIT License - see the LICENSE file for details.
