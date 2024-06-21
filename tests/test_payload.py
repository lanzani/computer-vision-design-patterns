# -*- coding: utf-8 -*-
import time
import unittest
from computer_vision_design_patterns.pipeline.payload import Payload


class PayloadTest(unittest.TestCase):
    def setUp(self):
        self.payload = Payload()

    def test_payload_is_immutable(self):
        with self.assertRaises(AttributeError):
            self.payload.timestamp = 1234567890

    def test_payload_has_timestamp(self):
        self.assertIsNotNone(self.payload.timestamp)

    def test_payload_timestamp_is_float(self):
        self.assertIsInstance(self.payload.timestamp, float)

    def test_payloads_have_unique_timestamps(self):
        time.sleep(0.000000000000000000001)
        payload2 = Payload()
        self.assertNotEqual(self.payload.timestamp, payload2.timestamp)

        print(self.payload.timestamp)
        print(payload2.timestamp)


if __name__ == "__main__":
    unittest.main()
