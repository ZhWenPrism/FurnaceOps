from http.client import HTTPConnection
import json
from pathlib import Path
import tempfile
import threading
import unittest

from app import connect, create_server


class NonFiniteMeasurementTest(unittest.TestCase):
    def test_nonfinite_observations_are_invalid_and_serialized_as_null(self):
        def reject_constant(value):
            self.fail(f"non-standard JSON value: {value}")

        with tempfile.TemporaryDirectory() as tmp:
            database = Path(tmp) / "data.sqlite3"
            with create_server(database) as server:
                with connect(database) as db:
                    db.execute("UPDATE assets SET value = ? WHERE id = 'D-01'", (float("inf"),))
                    db.execute("UPDATE measurements SET value = ? WHERE asset_id = 'D-01'", (-float("inf"),))
                thread = threading.Thread(target=server.serve_forever, daemon=True)
                thread.start()
                try:
                    def get(path):
                        client = HTTPConnection("127.0.0.1", server.server_port, timeout=3)
                        try:
                            client.request("GET", path)
                            response = client.getresponse()
                            self.assertEqual(response.status, 200)
                            return json.loads(response.read(), parse_constant=reject_constant)
                        finally:
                            client.close()

                    self.assertEqual(get("/api/summary")["quality_counts"]["invalid"], 1)
                    asset = get("/api/assets/D-01")["asset"]
                    self.assertEqual(asset["quality"], "invalid")
                    self.assertIsNone(asset["value"])
                    self.assertTrue(all(row["value"] is None for row in get("/api/assets/D-01/series")["items"]))
                finally:
                    server.shutdown()
                    thread.join()
