from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import sqlite3
import tempfile
import time
from threading import Barrier
import unittest
from unittest.mock import patch

from app import connect, initialize


class ConcurrentSeedTest(unittest.TestCase):
    def test_parallel_initializers_seed_one_complete_dataset(self):
        original_connect = sqlite3.connect

        def connect_with_delayed_seed(*args, **kwargs):
            db = original_connect(*args, **kwargs)
            delayed = False

            def trace(statement):
                nonlocal delayed
                if not delayed and statement.startswith("INSERT INTO assets"):
                    delayed = True
                    time.sleep(0.1)

            db.set_trace_callback(trace)
            return db

        with (tempfile.TemporaryDirectory() as tmp, ThreadPoolExecutor(max_workers=8) as pool,
              patch("app.sqlite3.connect", side_effect=connect_with_delayed_seed)):
            for attempt in range(3):
                database = Path(tmp) / f"seed-{attempt}.sqlite3"
                ready = Barrier(8)

                def start(_):
                    ready.wait(timeout=5)
                    initialize(database)

                list(pool.map(start, range(8)))
                with connect(database) as db:
                    self.assertEqual(db.execute("SELECT COUNT(*) FROM assets").fetchone()[0], 6)
                    self.assertEqual(db.execute("SELECT COUNT(*) FROM records").fetchone()[0], 30)
                    self.assertEqual(db.execute("SELECT COUNT(*) FROM measurements").fetchone()[0], 144)
