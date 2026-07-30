import sys
import os
import json
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from src.engine.transport import PayloadError
from src.engine.payload_validators import YahooPriceValidator

class TestPayloadValidators(unittest.TestCase):
    def setUp(self):
        self.validator = YahooPriceValidator()
        
        # Valid Yahoo Finance Payload
        self.valid_payload = json.dumps({
            "chart": {
                "result": [
                    {
                        "meta": {
                            "currency": "USD",
                            "symbol": "CZR",
                            "regularMarketPrice": 42.50
                        }
                    }
                ]
            }
        })

    def test_valid_payload_passes(self):
        """Mutation: None. Expected: Passes cleanly."""
        data = self.validator.validate(self.valid_payload)
        self.assertEqual(data["chart"]["result"][0]["meta"]["regularMarketPrice"], 42.50)

    def test_missing_root_key(self):
        """Mutation: Yahoo API changes root structure. Expected: PayloadError."""
        bad_payload = json.dumps({"data": {"result": []}})
        with self.assertRaises(PayloadError) as ctx:
            self.validator.validate(bad_payload)
        self.assertIn("Missing root key", str(ctx.exception))

    def test_missing_price_key(self):
        """Mutation: Yahoo removes 'regularMarketPrice'. Expected: PayloadError."""
        bad_payload = json.dumps({
            "chart": {
                "result": [
                    {
                        "meta": {
                            "currency": "USD",
                            "symbol": "CZR"
                        }
                    }
                ]
            }
        })
        with self.assertRaises(PayloadError) as ctx:
            self.validator.validate(bad_payload)
        self.assertIn("regularMarketPrice", str(ctx.exception))
        
    def test_malformed_json(self):
        """Mutation: Truncated JSON string. Expected: PayloadError."""
        bad_payload = '{"chart": {"result": [{"meta": {"curren'
        with self.assertRaises(PayloadError):
            self.validator.validate(bad_payload)

if __name__ == '__main__':
    print("\n=== RUNNING PAYLOAD VALIDATOR MUTATION SUITE ===")
    unittest.main(verbosity=2)
