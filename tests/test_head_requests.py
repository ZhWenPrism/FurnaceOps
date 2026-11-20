import unittest
import test_app as support


class HeadRequestsTest(unittest.TestCase):
    setUpClass = classmethod(support.APITest.setUpClass.__func__)
    tearDownClass = classmethod(support.APITest.tearDownClass.__func__)
    raw = support.APITest.raw
    def test_head_matches_get_headers_without_a_body(self):
        for path in ('/', '/app.js', '/api/health', '/api/records.csv', '/missing'):
            with self.subTest(path=path):
                status, body, headers = self.raw(path)
                head_status, head_body, head_headers = self.raw(path, method='HEAD')
                self.assertEqual(head_status, status)
                self.assertEqual(head_body, b'')
                self.assertEqual(head_headers['Content-Length'], str(len(body)))
                self.assertEqual(head_headers['Content-Type'], headers['Content-Type'])
