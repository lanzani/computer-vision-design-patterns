# -*- coding: utf-8 -*-
import pytest

from computer_vision_design_patterns.counter import ManualCounter


def test_manual_counter_initialization():
    counter = ManualCounter(threshold=5)
    assert counter.state == "inactive"
    assert counter.counter == 0
    assert counter.threshold == 5


def test_manual_counter_update():
    counter = ManualCounter(threshold=3)

    counter.update()
    assert counter.state == "inactive"
    assert counter.counter == 1

    counter.update()
    assert counter.state == "inactive"
    assert counter.counter == 2

    counter.update()
    assert counter.state == "active"
    assert counter.counter == 3


def test_manual_counter_reset():
    counter = ManualCounter(threshold=3)
    counter.update()
    counter.update()
    counter.update()
    assert counter.state == "active"
    assert counter.counter == 3

    counter.reset()
    assert counter.state == "inactive"
    assert counter.counter == 0


def test_manual_counter_is_active():
    counter = ManualCounter(threshold=2)
    assert not counter.is_active()

    counter.update()
    assert not counter.is_active()

    counter.update()
    assert counter.is_active()


def test_manual_counter_deactivate():
    counter = ManualCounter(threshold=1)
    counter.update()
    assert counter.is_active()

    counter.deactivate()
    assert not counter.is_active()
    assert counter.state == "inactive"


@pytest.mark.parametrize("threshold", [1, 5, 10])
def test_manual_counter_different_thresholds(threshold):
    counter = ManualCounter(threshold=threshold)

    for _ in range(threshold - 1):
        counter.update()
        assert not counter.is_active()

    counter.update()
    assert counter.is_active()
