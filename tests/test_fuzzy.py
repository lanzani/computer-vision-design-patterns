# -*- coding: utf-8 -*-
import pytest

from computer_vision_design_patterns.fuzzy import ConditionalBoolean


def test_conditional_boolean_initialization():
    def always_true():
        return True

    cb = ConditionalBoolean(always_true)
    assert callable(cb._expression)


def test_conditional_boolean_eval_no_args():
    def always_true():
        return True

    cb = ConditionalBoolean(always_true)
    assert cb.eval()


def test_conditional_boolean_eval_with_args():
    def greater_than(x, y):
        return x > y

    cb = ConditionalBoolean(greater_than)
    assert cb.eval(5, 3)
    assert not cb.eval(2, 7)


def test_conditional_boolean_with_lambda():
    cb = ConditionalBoolean(lambda x: x % 2 == 0)
    assert cb.eval(4)
    assert not cb.eval(7)


def test_conditional_boolean_with_complex_logic():
    def complex_logic(x, y, z):
        return x > y and y < z and x != z

    cb = ConditionalBoolean(complex_logic)
    assert cb.eval(5, 3, 4)
    assert not cb.eval(5, 4, 3)
    assert not cb.eval(3, 2, 3)


def test_conditional_boolean_with_exception():
    def divide(x, y):
        return x / y > 1

    cb = ConditionalBoolean(divide)
    assert cb.eval(4, 2)
    assert not cb.eval(2, 4)

    with pytest.raises(ZeroDivisionError):
        cb.eval(4, 0)


@pytest.mark.parametrize(
    "expression,args,expected",
    [
        (lambda x: x > 0, (1,), True),
        (lambda x: x > 0, (-1,), False),
        (lambda x, y: x == y, (2, 2), True),
        (lambda x, y: x == y, (2, 3), False),
    ],
)
def test_conditional_boolean_parametrized(expression, args, expected):
    cb = ConditionalBoolean(expression)
    assert cb.eval(*args) == expected
