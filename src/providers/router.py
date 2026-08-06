"""
SSR 2.0: AI Provider Router & Resilience Layer
Handles multi-provider fallback (Gemini -> OpenRouter), comma-separated 
API key rotation, 401 fail-fast dropping, and 429 exponential backoffs.
"""

import os
import time
import json
import logging
import requests
import threading
from typing import List, Dict

logger = logging.getLogger(__name__)

class ProviderRouter:
    def __init__(self):
        self._lock = threading.Lock()
        # Dynamically parse comma-separated API keys from the environment
        self.keys = {
            "gemini": self._parse_keys("GEMINI_API_KEY"),
            "openrouter": self._parse_keys("OPENROUTER_API_KEY")
        }
        self.settings = {}
        
        total_keys = sum(len(v) for v in self.keys.values())
        logger.info(f"[AI ROUTER] Initialized with {total_keys} total keys across providers.")

    def _parse_keys(self, env_var: str) -> List[str]:
        """Parses a comma-separated string of API keys into a clean list."""
        raw = os.environ.get(env_var, "")
        keys = [k.strip() for k in raw.split(",") if k.strip()]
        
        # Support GEMINI_API_KEY_1 through 10 fallback format
        for i in range(1, 11):
            val = os.environ.get(f"{env_var}_{i}", "")
            if val:
                keys.extend([k.strip() for k in val.split(",") if k.strip()])
                
        return keys

    def update_config(self, settings: dict):
        """Injects dynamic settings from The Brain (Google Sheets)."""
        self.settings = settings

    def generate(self, prompt: str, require_json: bool = False) -> str:
        """
        Executes the prompt against available providers. 
        Implements intelligent fallback and token rotation logic.
        """
        provider_order = ["gemini", "openrouter"]
        
        for provider in provider_order:
            while True:
                with self._lock:
                    keys = self.keys.get(provider, [])
                    if not keys:
                        break
                    current_key = keys[0]
                
                try:
                    if provider == "gemini":
                        return self._call_gemini(prompt, current_key, require_json)
                    elif provider == "openrouter":
                        return self._call_openrouter(prompt, current_key, require_json)
                        
                except requests.exceptions.HTTPError as e:
                    status_code = getattr(e.response, 'status_code', 500)
                    
                    if status_code == 401 or status_code == 403:
                        # FAIL-FAST: Unauthorized key. It's dead. Drop it permanently.
                        logger.warning(f"[AI ROUTER] {status_code} on {provider}. Purging dead key from rotation.")
                        with self._lock:
                            keys_ref = self.keys.get(provider, [])
                            if keys_ref and keys_ref[0] == current_key:
                                keys_ref.pop(0)
                        
                    elif status_code == 429:
                        # RATE LIMIT: Move the exhausted key to the back of the queue and pause briefly.
                        logger.warning(f"[AI ROUTER] 429 Rate Limit on {provider}. Rotating to next key.")
                        with self._lock:
                            keys_ref = self.keys.get(provider, [])
                            if keys_ref and keys_ref[0] == current_key:
                                keys_ref.append(keys_ref.pop(0))
                        time.sleep(1.5) # Graceful backoff
                        
                    elif status_code >= 500:
                        # VENDOR OUTAGE: The provider is down. Skip to the next provider immediately.
                        logger.error(f"[AI ROUTER] 5xx Vendor Outage on {provider}. Switching providers.")
                        break 
                        
                    else:
                        logger.error(f"[AI ROUTER] Unexpected HTTP {status_code} from {provider}: {e}")
                        break
                        
                except Exception as e:
                    logger.error(f"[AI ROUTER] Unknown exception connecting to {provider}: {e}")
                    break # Abort this provider, try the next
                    
        # If the loop exhausts without returning, we are completely out of AI credits/keys.
        return "EXHAUSTED"

    def _call_gemini(self, prompt: str, api_key: str, require_json: bool) -> str:
        """Executes API call to Google Gemini REST API."""
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={api_key}"
        headers = {"Content-Type": "application/json"}
        
        system_prompt = "You are a specialized corporate events data extractor."
        if require_json:
            system_prompt += " You must respond strictly with valid JSON. Do not include markdown formatting or commentary."
            
        payload = {
            "system_instruction": {
                "parts": [{"text": system_prompt}]
            },
            "contents": [{
                "parts": [{"text": prompt}]
            }],
            "generationConfig": {
                "temperature": 0.0
            }
        }
        
        if require_json:
            payload["generationConfig"]["responseMimeType"] = "application/json"
            
        response = requests.post(url, headers=headers, json=payload, timeout=20)
        response.raise_for_status()
        
        data = response.json()
        try:
            return data["candidates"][0]["content"]["parts"][0]["text"]
        except (KeyError, IndexError):
            logger.error(f"[AI ROUTER] Unexpected Gemini response format: {data}")
            raise requests.exceptions.HTTPError(response=response)

    def _call_openrouter(self, prompt: str, api_key: str, require_json: bool) -> str:
        """Executes API call to OpenRouter."""
        url = "https://openrouter.ai/api/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/tonyfonda-eng/SSR",
            "X-Title": "Special Situations Radar"
        }
        
        system_prompt = "You are a specialized corporate events data extractor."
        if require_json:
            system_prompt += " You must respond strictly with valid JSON. Do not include markdown formatting or commentary."
            
        payload = {
            "model": "google/gemini-1.5-flash", 
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.0
        }
        
        if require_json:
            payload["response_format"] = {"type": "json_object"}
            
        response = requests.post(url, headers=headers, json=payload, timeout=20)
        response.raise_for_status()
        
        data = response.json()
        return data["choices"][0]["message"]["content"]
