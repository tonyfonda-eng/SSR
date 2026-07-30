import sys
import os
import unittest
from unittest.mock import patch, Mock
import requests
from requests.exceptions import Timeout, HTTPError

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from src.engine.transport import ResilientTransport, TransportPolicy, TransportError, PayloadError, CircuitOpenError

class TestTransportMutations(unittest.TestCase):
    def setUp(self):
        # We use a fast policy for testing so we don't sit through long backoffs
        self.transport = ResilientTransport(quarantine_dir="test_quarantine")
        self.policy = TransportPolicy(name="TEST_API", max_retries=2, base_backoff=0.01, require_json=True)
        self.url = "https://api.example.com/data"

    @patch('requests.Session.get')
    def test_mutation_503_retry_success(self, mock_get):
        """Mutation: Server returns 503 twice, then succeeds on 3rd try."""
        fail_resp = Mock()
        fail_resp.status_code = 503
        
        success_resp = Mock()
        success_resp.status_code = 200
        success_resp.ok = True
        success_resp.headers = {"Content-Type": "application/json"}
        
        mock_get.side_effect = [fail_resp, fail_resp, success_resp]
        
        resp = self.transport.get(self.url, self.policy)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(mock_get.call_count, 3)

    @patch('requests.Session.get')
    def test_mutation_timeout_circuit_breaker(self, mock_get):
        """Mutation: Server continuously times out. Circuit breaker should trip."""
        mock_get.side_effect = Timeout("Connection timed out")
        
        with self.assertRaises(TransportError):
            self.transport.get(self.url, self.policy)
            
        # Circuit should now be open for api.example.com
        with self.assertRaises(CircuitOpenError):
            self.transport.get(self.url, self.policy)

    @patch('requests.Session.get')
    def test_mutation_404_immediate_fail(self, mock_get):
        """Mutation: Server returns 404 Not Found. Should NOT retry."""
        fail_resp = Mock()
        fail_resp.status_code = 404
        fail_resp.ok = False
        fail_resp.raise_for_status.side_effect = HTTPError("404 Client Error")
        
        mock_get.return_value = fail_resp
        
        with self.assertRaises(HTTPError):
            self.transport.get(self.url, self.policy)
        self.assertEqual(mock_get.call_count, 1) # Proves no retries occurred

    @patch('requests.Session.get')
    def test_mutation_html_payload_injection(self, mock_get):
        """Mutation: Server returns 200 OK, but payload is a captive portal HTML page."""
        bad_resp = Mock()
        bad_resp.status_code = 200
        bad_resp.ok = True
        bad_resp.headers = {"Content-Type": "text/html"}
        bad_resp.text = "<html><body>Maintenance</body></html>"
        
        mock_get.return_value = bad_resp
        
        with self.assertRaises(PayloadError):
            self.transport.get(self.url, self.policy)
            
        # Verify Quarantine Queue caught it
        files = os.listdir("test_quarantine")
        self.assertGreater(len(files), 0)

if __name__ == '__main__':
    print("\n=== RUNNING TRANSPORT MUTATION SUITE ===")
    unittest.main(verbosity=2)
