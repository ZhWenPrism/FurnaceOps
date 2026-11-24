import csv
import io
import unittest

import test_app as support
from app import connect


class TimestampOrderTest(unittest.TestCase):
    setUpClass = classmethod(support.APITest.setUpClass.__func__)
    tearDownClass = classmethod(support.APITest.tearDownClass.__func__)
    raw = support.APITest.raw
    data = support.APITest.data

    def test_record_json_and_csv_sort_instants_across_offsets(self):
        earlier = "2026-10-11T11:00:00+08:00"
        later = "2026-10-11T05:00:00+00:00"
        with connect(self.db) as db:
            for record_id, timestamp in [("T-EARLY", earlier), ("T-LATE", later)]:
                db.execute("INSERT INTO records VALUES (?,?,?,?,?,?,?)",
                           (record_id, "D-01", timestamp, "检查", "Check", "Recorded", ""))
        rows = self.data("/api/records?asset_id=D-01")["items"]
        self.assertEqual([row["id"] for row in rows[:2]], ["T-LATE", "T-EARLY"])
        status, body, _ = self.raw("/api/records.csv?asset_id=D-01")
        self.assertEqual(status, 200)
        exported = list(csv.reader(io.StringIO(body.decode("utf-8-sig"))))
        self.assertEqual([row[0] for row in exported[1:3]], ["T-LATE", "T-EARLY"])

    def test_series_sorts_instants_across_offsets(self):
        earlier = "2026-10-11T14:00:00+08:00"
        later = "2026-10-11T06:30:00+00:00"
        with connect(self.db) as db:
            db.executemany("INSERT INTO measurements VALUES (?,?,?)",
                           [("D-01", earlier, 31.0), ("D-01", later, 32.0)])
        rows = self.data("/api/assets/D-01/series")["items"]
        self.assertEqual([row["timestamp"] for row in rows[-2:]], [earlier, later])
