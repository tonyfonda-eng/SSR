import sys
from src.ai import _generate_with_retry, clients

print(f"Initial clients: {clients}")

# We will mock the clients to throw exceptions
class MockOpenRouterClient:
    class chat:
        class completions:
            @staticmethod
            def create(*args, **kwargs):
                class MockException(Exception):
                    pass
                raise MockException("Error code: 404 - {'error': {'message': 'This model is unavailable for free. The paid version is available now - use this slug instead: meta-llama/llama-3.3-70b-instruct', 'code': 404}, 'user_id': 'user_123'}")

class MockGeminiClient:
    class models:
        @staticmethod
        def generate_content(*args, **kwargs):
            class MockException(Exception):
                pass
            raise MockException("Quota exceeded for quota metric 'Generate requests' and limit 'Generate requests per day'")

# Replace clients with our mocks
clients.clear()
clients.append(("openrouter", MockOpenRouterClient()))
clients.append(("gemini", MockGeminiClient()))

try:
    _generate_with_retry("test prompt")
except Exception as e:
    print(f"Caught final exception: {e}")

print(f"Final clients list: {clients}")
