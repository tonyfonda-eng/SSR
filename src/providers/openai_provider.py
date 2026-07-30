import json
import os
from openai import OpenAI
from src.providers.base_provider import AIProvider

class OpenAICompatibleProvider(AIProvider):
    def __init__(self, model_id: str, base_url: str):
        # Dynamically accepts keys for Grok (X.AI), Groq, or native OpenAI paths
        api_key = os.environ.get("SECONDARY_API_KEY")
        self.client = OpenAI(api_key=api_key, base_url=base_url)
        self.model_id = model_id

    def research(self, text: str, prompt: str) -> dict:
        response = self.client.chat.completions.create(
            model=self.model_id,
            messages=[
                {"role": "system", "content": prompt},
                {"role": "user", "content": text}
            ],
            response_format={"type": "json_object"}
        )
        return json.loads(response.choices[0].message.content)
