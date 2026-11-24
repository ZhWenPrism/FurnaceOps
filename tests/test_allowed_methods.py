import unittest

import test_app as support


class AllowedMethodsTest(unittest.TestCase):
    setUpClass = classmethod(support.APITest.setUpClass.__func__)
    tearDownClass = classmethod(support.APITest.tearDownClass.__func__)
    raw = support.APITest.raw

    def test_rejected_write_methods_advertise_read_methods(self):
        for method in ("POST", "PUT", "DELETE", "PATCH"):
            with self.subTest(method=method):
                status, _, headers = self.raw("/api/assets", method)
                self.assertEqual(status, 405)
                self.assertEqual(headers.get("Allow"), "GET, HEAD")

    def test_read_methods_remain_available(self):
        get_status, body, _ = self.raw("/api/assets")
        head_status, head_body, headers = self.raw("/api/assets", "HEAD")
        self.assertEqual((get_status, head_status), (200, 200))
        self.assertEqual(head_body, b"")
        self.assertEqual(int(headers["Content-Length"]), len(body))
