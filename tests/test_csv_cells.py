import csv
import io
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Thread
from unittest import TestCase
from urllib.request import ProxyHandler, build_opener

from app import connect, create_server, safe_csv


class CSVCellTest(TestCase):
    def test_leading_controls_are_escaped(self):
        for value in ("\ttext", "\rtext", "\ntext", " \ttext", " +1"):
            with self.subTest(value=value):
                self.assertEqual(safe_csv(value), "'" + value)
        self.assertEqual(safe_csv(" ordinary text"), " ordinary text")

    def test_source_metadata_is_escaped(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "fixture.sqlite3"
            with create_server(path) as server:
                with connect(path) as db:
                    db.execute("UPDATE metadata SET value=? WHERE key='source'", ("=1+1",))
                thread = Thread(target=server.serve_forever)
                thread.start()
                try:
                    opener = build_opener(ProxyHandler({}))
                    with opener.open(f"http://127.0.0.1:{server.server_port}/api/records.csv", timeout=3) as response:
                        rows = list(csv.reader(io.StringIO(response.read().decode("utf-8-sig"))))
                    self.assertTrue(rows[1:])
                    self.assertTrue(all(row[-1] == "'=1+1" for row in rows[1:]))
                finally:
                    server.shutdown()
                    thread.join()
