import os
import unittest
from unittest.mock import patch, MagicMock
import requests

# Set mock comma-separated API keys in the environment before importing the router
os.environ["ANTHROPIC_API_KEY"] = "sk-ant-key1, sk-ant-key2"
os.environ["OPENAI_API_KEY"] = "sk-oai-key1"

from src.providers.router import ProviderRouter

class TestProviderRouterResilience(unittest.TestCase):

    @patch('requests.post')
    def test_401_fail_fast_purging(self, mock_post):
        print("\n[TEST] Running 401 Unauthorized Fail-Fast Key Purging Test...")
        
        # Simulate a 401 error on the first Anthropic key, then success on the second key
        mock_resp_401 = MagicMock()
        mock_resp_401.status_code = 401
        mock_resp_401.text = "Unauthorized"
        
        mock_resp_success = MagicMock()
        mock_resp_success.status_code = 200
        mock_resp_success.json.return_value = {
            "content": [{"text": "Mocked Anthropic Response"}]
        }
        
        # First call raises HTTPError 401, second call succeeds
        mock_post.side_effect = [
            requests.exceptions.HTTPError(response=mock_resp_401),
            mock_resp_success
        ]
        
        router = ProviderRouter()
        # Initially we have 2 anthropic keys
        self.assertEqual(len(router.keys["anthropic"]), 2)
        
        result = router.generate("Test prompt")
        
        # Verify it successfully fell back to key 2 after purging key 1
        self.assertEqual(result, "Mocked Anthropic Response")
        self.assertEqual(len(router.keys["anthropic"]), 1)
        self.assertEqual(router.keys["anthropic"][0], "sk-ant-key2")
        print("[PASS] 401 successfully dropped the dead key and rotated to the backup key.")

    @patch('requests.post')
    def test_429_rate_limit_rotation(self, mock_post):
        print("\n[TEST] Running 429 Rate Limit Key Rotation Test...")
        
        # Simulate a 429 rate limit on key 1, then success on key 2
        mock_resp_429 = MagicMock()
        mock_resp_429.status_code = 429
        mock_resp_429.text = "Rate Limited"
        
        mock_resp_success = MagicMock()
        mock_resp_success.status_code = 200
        mock_resp_success.json.return_value = {
            "content": [{"text": "Success after rotation"}]
        }
        
        mock_post.side_effect = [
            requests.exceptions.HTTPError(response=mock_resp_429),
            mock_resp_success
        ]
        
        router = ProviderRouter()
        initial_key_order = list(router.keys["anthropic"])
        
        result = router.generate("Test prompt")
        
        self.assertEqual(result, "Success after rotation")
        # 429 should move the exhausted key to the back rather than deleting it
        self.assertEqual(len(router.keys["anthropic"]), 2)
        self.assertEqual(router.keys["anthropic"][0], initial_key_order[1])
        self.assertEqual(router.keys["anthropic"][1], initial_key_order[0])
        print("[PASS] 429 successfully backed off and rotated the rate-limited key to the back of the queue.")

if __name__ == "__main__":
    unittest.main()
