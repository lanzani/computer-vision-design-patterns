# -*- coding: utf-8 -*-
import time

from computer_vision_design_patterns.event import CountdownEvent, TimeEvent


def demonstrate_time_event():
    print("\n=== TimeEvent Demonstration ===")

    # Scenario 1: Basic timeout behavior
    print("Basic TimeEvent")
    event = TimeEvent(2)
    event.trigger()

    for i in range(4):
        active = event.is_active()
        print(f"Second {i}: Event is {'active' if active else 'inactive'}")
        time.sleep(1)

    # Scenario 2: Retriggering resets the timer
    print("Retriggering...")
    event.trigger()
    time.sleep(1)
    print("After 1 second:", event.is_active())

    print("Retriggering...")
    event.trigger()
    print("After 1 second:", event.is_active())
    time.sleep(3)
    print("After 3 seconds:", event.is_active())


def demonstrate_countdown_event():
    print("\n=== CountdownEvent Demonstration ===")

    # Scenario 1: Basic countdown behavior
    print("Basic CountdownEvent")
    event = CountdownEvent(3)
    event.trigger()

    for i in range(5):
        active = event.is_active()
        print(f"Second {i}: Event is {'active' if active else 'inactive'}")
        time.sleep(1)

    # Scenario 2: Reset behavior
    print("\n2. Resetting CountdownEvent")
    event = CountdownEvent(2)
    event.trigger()
    print("Started countdown")
    time.sleep(3)
    print("After 3 seconds:", event.is_active())

    print("Resetting...")
    event.reset()
    print("After reset:", event.is_active())


if __name__ == "__main__":
    demonstrate_time_event()
    demonstrate_countdown_event()
