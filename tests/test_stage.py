# -*- coding: utf-8 -*-
import time
import unittest
from computer_vision_design_patterns.pipeline.payload import Payload
from computer_vision_design_patterns.pipeline.sample_stage import DummyStageNtoN
import multiprocessing as mp


class TestStageNtoN(unittest.TestCase):
    def setUp(self):
        self.payload = Payload()
        self.stage = DummyStageNtoN("stage", 2, 1)

    def test_stage_get_from_left_empty(self):
        with self.assertRaises(ValueError):
            self.stage.get_from_left()

    def test_get_from_left_none(self):
        self.stage.input_queues = {"key1": mp.Queue()}
        self.assertEqual(self.stage.get_from_left(), None)

    def test_get_from_left_value(self):
        pass
