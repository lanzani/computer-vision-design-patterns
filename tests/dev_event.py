# -*- coding: utf-8 -*-
import time

from computer_vision_design_patterns.event import TimeEvent


def main():
    event = TimeEvent(2)

    event.trigger()
    for _ in range(10):
        print(event.is_active())
        time.sleep(1)


if __name__ == "__main__":
    main()
