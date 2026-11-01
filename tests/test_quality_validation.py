import unittest

from app import SNAPSHOT, quality


class ObservationQualityTest(unittest.TestCase):
    def test_malformed_observation_timestamp_is_invalid(self):
        self.assertEqual(quality({"value": 1.0, "observed_at": "not-a-timestamp"}, SNAPSHOT), "invalid")


    def test_naive_observation_timestamp_is_invalid(self):
        self.assertEqual(quality({"value": 1.0, "observed_at": "2026-10-11T09:59:00"}, SNAPSHOT), "invalid")


    def test_missing_observation_still_has_missing_quality(self):
        self.assertEqual(quality({"value": 1.0, "observed_at": None}, SNAPSHOT), "missing")

