# -*- coding: utf-8 -*-
import multiprocessing as mp
import threading
from unittest.mock import MagicMock, patch

import pytest

from computer_vision_design_patterns.pipeline import Payload, Stage
from computer_vision_design_patterns.pipeline.stage import PoisonPill, StageExecutor, StageType


class MockStage(Stage):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.pre_run_called = False
        self.post_run_called = False

    def pre_run(self):
        self.pre_run_called = True

    def post_run(self):
        self.post_run_called = True

    def process(self, key: str, payload: Payload | None) -> Payload | None:
        return super().process(key, payload)


@pytest.fixture
def mock_stage():
    return MockStage(StageType.One2One, StageExecutor.THREAD)


def test_stage_initialization(mock_stage):
    assert isinstance(mock_stage, Stage)
    assert mock_stage._stage_type == StageType.One2One
    assert mock_stage._stage_executor == StageExecutor.THREAD
    assert isinstance(mock_stage._running, threading.Event)
    assert isinstance(mock_stage._worker, threading.Thread)


def test_stage_pre_run(mock_stage):
    mock_stage.pre_run()
    assert mock_stage.pre_run_called


def test_stage_post_run(mock_stage):
    mock_stage.post_run()
    assert mock_stage.post_run_called


def test_stage_process_poison_pill(mock_stage):
    mock_stage._running.set()
    result = mock_stage.process("test_key", PoisonPill())
    assert result is None
    assert not mock_stage._running.is_set()


@pytest.mark.parametrize("stage_executor", [StageExecutor.THREAD, StageExecutor.PROCESS])
def test_stage_executor_types(stage_executor):
    stage = MockStage(StageType.One2One, stage_executor)
    if stage_executor == StageExecutor.THREAD:
        assert isinstance(stage._worker, threading.Thread)
    else:
        assert isinstance(stage._worker, mp.Process)


def test_invalid_stage_executor():
    with pytest.raises(ValueError):
        MockStage(StageType.One2One, "INVALID")


@patch("multiprocessing.Queue")
def test_get_from_left(mock_queue, mock_stage):
    mock_queue.return_value.get.return_value = "test_payload"
    mock_stage.input_queues = {"test_key": mock_queue.return_value}
    result = mock_stage.get_from_left("test_key")
    assert result == "test_payload"


@patch("multiprocessing.Queue")
def test_put_to_right(mock_queue, mock_stage):
    mock_stage._output_queues = {"test_key": mock_queue.return_value}
    mock_stage.put_to_right("test_key", "test_payload")
    mock_queue.return_value.put.assert_called_once_with("test_payload", timeout=0.1)


def test_link_stages():
    stage1 = MockStage(StageType.One2One, StageExecutor.THREAD)
    stage2 = MockStage(StageType.One2One, StageExecutor.THREAD)
    stage1.link(stage2, "test_key")
    assert "test_key" in stage1._output_queues
    assert "test_key" in stage2.input_queues
    assert stage1._output_queues["test_key"] == stage2.input_queues["test_key"]


def test_unlink_stages():
    stage = MockStage(StageType.One2One, StageExecutor.THREAD)
    stage.input_queues = {"test_stream_1": MagicMock(), "test_stream_2": MagicMock()}
    stage._output_queues = {"test_stream_1": MagicMock(), "test_stream_2": MagicMock()}
    stage.unlink("test_stream_1")
    assert "test_stream_1" not in stage.input_queues
    assert "test_stream_1" not in stage._output_queues
    assert "test_stream_2" in stage.input_queues
    assert "test_stream_2" in stage._output_queues


@patch("threading.Thread.start")
def test_start_stage(mock_start, mock_stage):
    mock_stage.start()
    assert mock_stage._running.is_set()
    mock_start.assert_called_once()


@patch("threading.Thread.join")
def test_stop_and_join_stage(mock_join, mock_stage):
    mock_stage._running.set()
    mock_stage.stop()
    assert not mock_stage._running.is_set()
    mock_stage.join()
    mock_join.assert_called_once()
