# -*- coding: utf-8 -*-
import time

from computer_vision_design_patterns.event import TimeEvent


def main():
    event = TimeEvent(2)

    event.trigger()

    print(event.state)

    event.update_state()
    print(event.state)

    time.sleep(3)
    event.update_state()
    print(event.state)


if __name__ == "__main__":
    main()
