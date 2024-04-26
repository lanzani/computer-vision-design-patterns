# -*- coding: utf-8 -*-
import time

from computer_vision_design_patterns.event import TimeEvent


def main():
    event = TimeEvent(2)

    # event.trigger()

    print(event.state)



if __name__ == "__main__":
    main()
