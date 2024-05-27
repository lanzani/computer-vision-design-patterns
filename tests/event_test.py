# -*- coding: utf-8 -*-
import time

from computer_vision_design_patterns.event import TimeEvent


def main():
    event = TimeEvent(2)


    for _ in range(10):
        event.trigger()
        print(event.retrive_state())
        time.sleep(1)


if __name__ == "__main__":
    main()
