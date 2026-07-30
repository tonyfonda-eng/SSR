import json
import os
from google import genai
from google.genai import types
from src.providers.base_provider import AIProvider

class GeminiProvider(AIProvider):
    def __init__(self, model_id: str):
        self.client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))
        self.model_id = model_id

    def research(self, text: str, prompt: str) -> dict:
        response = self.client.models.generate_content(
            model=self.model_id,
            contents=[prompt, text],
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
            )
        )
        return json.loads(response.text)
