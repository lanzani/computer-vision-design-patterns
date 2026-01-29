# -*- coding: utf-8 -*-
from unittest.mock import patch

import pytest

from computer_vision_design_patterns.event import CountdownEvent, TimeEvent


@pytest.fixture
def mock_time():
    with patch("time.time") as mock_time:
        mock_time.return_value = 0
        yield mock_time


class TestTimeEvent:
    def test_time_event_initialization(self):
        event = TimeEvent(event_seconds_duration=5)
        assert event.state == "inactive"
        assert event._event_seconds_duration == 5
        assert event._last_call_time is None

    def test_time_event_trigger(self, mock_time):
        event = TimeEvent(event_seconds_duration=5)
        event.trigger()
        assert event.state == "active"
        assert event._last_call_time == 0

    def test_time_event_is_active(self, mock_time):
        event = TimeEvent(event_seconds_duration=5)
        event.trigger()

        assert event.is_active()

        mock_time.return_value = 4
        assert event.is_active()

        mock_time.return_value = 5.1
        assert not event.is_active()

    def test_time_event_multiple_triggers(self, mock_time):
        event = TimeEvent(event_seconds_duration=5)
        event.trigger()

        mock_time.return_value = 2
        event.trigger()
        assert event.is_active()

        mock_time.return_value = 6
        assert event.is_active()

        mock_time.return_value = 7.1
        assert not event.is_active()


class TestCountdownEvent:
    def test_countdown_event_initialization(self):
        event = CountdownEvent(countdown_duration=5)
        assert event.state == "inactive"
        assert event._countdown_duration == 5
        assert event._last_call_time is None

    def test_countdown_event_trigger(self, mock_time):
        event = CountdownEvent(countdown_duration=5)
        event.trigger()
        assert event.state == "inactive"
        assert event._last_call_time == 0

    def test_countdown_event_is_active(self, mock_time):
        event = CountdownEvent(countdown_duration=5)
        event.trigger()

        assert not event.is_active()

        mock_time.return_value = 4
        assert not event.is_active()

        mock_time.return_value = 5.1
        assert event.is_active()

    def test_countdown_event_reset(self, mock_time):
        event = CountdownEvent(countdown_duration=5)
        event.trigger()

        mock_time.return_value = 6
        assert event.is_active()

        event.reset()
        assert not event.is_active()
        assert event._last_call_time is None
        assert event.state == "inactive"

    def test_countdown_event_multiple_triggers(self, mock_time):
        event = CountdownEvent(countdown_duration=5)
        event.trigger()

        mock_time.return_value = 2
        event.trigger()
        assert not event.is_active()

        mock_time.return_value = 6
        assert event.is_active()

        mock_time.return_value = 7.1
        assert event.is_active()
