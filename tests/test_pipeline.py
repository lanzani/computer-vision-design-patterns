# -*- coding: utf-8 -*-

import pytest
from unittest.mock import Mock

from computer_vision_design_patterns.pipeline import Stage, Pipeline


@pytest.fixture
def mock_stage():
    return Mock(spec=Stage)


@pytest.fixture
def pipeline():
    return Pipeline()


def test_pipeline_initialization(pipeline):
    assert isinstance(pipeline, Pipeline)
    assert pipeline.stages == []


def test_add_stage(pipeline, mock_stage):
    pipeline.add_stage(mock_stage)
    assert pipeline.stages == [mock_stage]


def test_link_stages(pipeline):
    stage1 = Mock(spec=Stage)
    stage2 = Mock(spec=Stage)
    Pipeline.link_stages(stage1, stage2, "test_key")
    stage1.link.assert_called_once_with(stage2, "test_key")


def test_unlink(pipeline, mock_stage):
    pipeline.stages = [mock_stage, mock_stage]
    pipeline.unlink("test_key")
    assert mock_stage.unlink.call_count == 2
    mock_stage.unlink.assert_called_with("test_key")


def test_unlink_removes_dead_stages(pipeline):
    live_stage = Mock(spec=Stage)
    live_stage.is_alive.return_value = True
    dead_stage = Mock(spec=Stage)
    dead_stage.is_alive.return_value = False
    pipeline.stages = [live_stage, dead_stage]
    pipeline.unlink("test_key")
    assert pipeline.stages == [live_stage]


def test_start(pipeline, mock_stage):
    mock_stage.is_alive.return_value = False
    pipeline.stages = [mock_stage, mock_stage]
    pipeline.start()
    assert mock_stage.start.call_count == 2


def test_stop(pipeline, mock_stage):
    pipeline.stages = [mock_stage, mock_stage]
    pipeline.stop()
    assert mock_stage.stop.call_count == 2
    assert mock_stage.join.call_count == 2


def test_stop_all_stages(pipeline, mock_stage):
    mock_stage._output_queues = {"queue1": Mock(), "queue2": Mock()}
    pipeline.stages = [mock_stage, mock_stage]
    pipeline.stop_all_stages()
    assert mock_stage._output_queues["queue1"].put.call_count == 2
    assert mock_stage._output_queues["queue2"].put.call_count == 2
    assert mock_stage.stop.call_count == 2
    assert mock_stage.join.call_count == 2


# def test_chain_poison_pill(pipeline):
#     stage1 = Mock(spec=Stage)
#     stage2 = Mock(spec=Stage)
#     pipeline.stages = [stage1, stage2]
#     pipeline.chain_poison_pill(type(stage1))
#     stage1.poison_pill.assert_called_once()
#     stage2.poison_pill.assert_not_called()
#     assert stage1.join.call_count == 1
#     assert stage2.join.call_count == 1


def test_flush(pipeline, mock_stage):
    pipeline.stages = [mock_stage, mock_stage]
    pipeline.flush()
    assert pipeline.stages == []
