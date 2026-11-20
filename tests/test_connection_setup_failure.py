import sqlite3
import unittest
from unittest.mock import MagicMock, patch
from app import connect


class ConnectionSetupFailureTest(unittest.TestCase):
    def test_failed_setup_closes_the_connection(self):
        con = MagicMock()
        con.execute.side_effect = sqlite3.OperationalError("setup failed")
        with patch("app.sqlite3.connect", return_value=con):
            with self.assertRaisesRegex(sqlite3.OperationalError, "setup failed"):
                with connect("unused.sqlite3"):
                    self.fail("setup failure reached the caller")
        con.close.assert_called_once()
