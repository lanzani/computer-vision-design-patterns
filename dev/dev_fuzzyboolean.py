# -*- coding: utf-8 -*-
from computer_vision_design_patterns.fuzzy import ConditionalBoolean


def main():
    conditional_boolean = ConditionalBoolean(lambda x, y: 10 < x < 20 and y > 10)

    print(conditional_boolean.eval(15, 10))


if __name__ == "__main__":
    main()
