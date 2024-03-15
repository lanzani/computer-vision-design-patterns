import time

from computer_vision_design_patterns.counter import ManualCounter


def main():
    counter = ManualCounter(5)

    for _ in range(10):
        counter.update()
        print(counter.is_active())
        time.sleep(1)

    counter.reset()

    counter.reset()

    for _ in range(10):
        counter.update()
        print(counter.is_active())
        time.sleep(1)


if __name__ == "__main__":
    main()
