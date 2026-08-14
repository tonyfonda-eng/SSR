import unittest
from unittest.mock import patch, MagicMock
import requests
from src.providers.router import ProviderRouter
from src.ai import parse_classification_output, ParsedAIPayload

class TestAIRouter(unittest.TestCase):
    def setUp(self):
        self.router = ProviderRouter()
        self.router.keys = {
            "gemini": ["fake_gemini_key"],
            "openrouter": ["fake_or_key"]
        }
        self.router.update_config([{"Setting Name": "Default AI Model", "Value": "Gemini-1.5-Pro"}])
        
    @patch('src.providers.router.requests.post')
    def test_gemini_success(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "candidates": [
                {
                    "content": {
                        "parts": [{"text": '{"classification": "Merger", "rationale": "Test"}'}]
                    }
                }
            ],
            "usageMetadata": {"promptTokenCount": 10, "candidatesTokenCount": 5}
        }
        mock_post.return_value = mock_resp
        
        result = self.router.generate("Test prompt", require_json=True)
        self.assertIn("Merger", result)
        
        # Verify endpoint has -latest
        args, kwargs = mock_post.call_args
        self.assertTrue("gemini-1.5-pro-latest" in args[0])
        
    @patch('src.providers.router.requests.post')
    def test_openrouter_fallback(self, mock_post):
        # First call fails (Gemini 404)
        mock_resp_gemini = MagicMock()
        mock_resp_gemini.status_code = 404
        mock_resp_gemini.raise_for_status.side_effect = requests.exceptions.HTTPError(response=mock_resp_gemini)
        
        # Second call succeeds (OpenRouter)
        mock_resp_or = MagicMock()
        mock_resp_or.status_code = 200
        mock_resp_or.json.return_value = {
            "choices": [
                {"message": {"content": '{"classification": "Acquisition", "rationale": "OR test"}'}}
            ],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5}
        }
        
        mock_post.side_effect = [mock_resp_gemini.raise_for_status.side_effect, mock_resp_or]
        
        result = self.router.generate("Test prompt", require_json=True)
        self.assertIn("Acquisition", result)
        
        # Verify OpenRouter was called without response_format since it's a google model
        self.assertEqual(mock_post.call_count, 2)
        or_kwargs = mock_post.call_args_list[1][1]
        self.assertNotIn("response_format", or_kwargs.get("json", {}))
        
    @patch('src.providers.router.requests.post')
    def test_malformed_provider_responses_fail_safely(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        # Missing 'candidates' structure
        mock_resp.json.return_value = {"error": "malformed format"}
        mock_post.return_value = mock_resp
        
        result = self.router.generate("Test prompt", require_json=True)
        # Router should return TIMEOUT after failing through all providers due to parsing exceptions
        self.assertEqual(result, "TIMEOUT")
        
    def test_provider_exhaustion_distinguishable(self):
        # No keys available
        self.router.keys = {"gemini": [], "openrouter": []}
        result = self.router.generate("Test prompt")
        self.assertEqual(result, "EXHAUSTED")
        
        parsed = parse_classification_output(result)
        self.assertEqual(parsed.strategy, "EXHAUSTED")
        # Distinguishable from 0.0 confidence (which would have a valid strategy but 0 confidence)
        self.assertEqual(parsed.confidence_score, 0.0)

if __name__ == '__main__':
    unittest.main()
