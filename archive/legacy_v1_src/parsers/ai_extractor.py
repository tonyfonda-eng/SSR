import json
from google import genai
from google.genai import types

class AIExtractor:
    def __init__(self):
        self.client = genai.Client()

    def analyze_text(self, text: str) -> dict:
        prompt = """
        You are an expert event-driven financial analyst. Extract key event details from the text.
        Return ONLY a valid JSON object with these exact keys:
        - ticker (string)
        - event_type (string)
        - defined_cash_amount (string or null)
        - premium_vs_market (string or null)
        - implied_volatility_notes (string or null)
        - extraction_confidence (float between 0.0 and 1.0)
        - research_confidence (float between 0.0 and 1.0)
        """
        response = self.client.models.generate_content(
            model='gemini-3.5-flash',
            contents=[prompt, text],
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
            )
        )
        return json.loads(response.text)
