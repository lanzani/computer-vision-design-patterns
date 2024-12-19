# Computer Vision Design Patterns - Event System

A flexible and thread-safe event handling system that provides different types of time-based events for computer vision applications.

# Installation

To install the package, you can use either **pip**:

```bash
pip install computer-vision-design-patterns
```

or **poetry**:

```bash
poetry add computer-vision-design-patterns
```

You can also install the package from the source code by cloning the repository and running:

```bash
poetry install
```

# Features

## Events

- TimeEvent: Auto-deactivating after duration
- CountdownEvent: Activation after countdown

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

Check the `dev/dev_event.py` file for comprehensive examples of both event types.

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
