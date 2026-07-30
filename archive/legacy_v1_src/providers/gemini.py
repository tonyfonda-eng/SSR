import os
from google import genai
from src.providers.base_ai import BaseAIProvider

class GeminiProvider(BaseAIProvider):
    def __init__(self):
        self.client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))

    def classify(self, text: str) -> str:
        response = self.client.models.generate_content(
            model='gemini-2.5-flash',
            contents=text,
        )
        return response.text
