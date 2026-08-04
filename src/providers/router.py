"""
SSR 2.0: AI Provider Router & Resilience Layer
Handles multi-provider fallback (Anthropic -> OpenAI), comma-separated 
API key rotation, 401 fail-fast dropping, and 429 exponential backoffs.
"""

import os
import time
import json
import logging
import requests
from typing import List, Dict

logger = logging.getLogger(__name__)

class ProviderRouter:
    def __init__(self):
        # Dynamically parse comma-separated API keys from the environment
        self.keys = {
            "anthropic": self._parse_keys("ANTHROPIC_API_KEY"),
            "openai": self._parse_keys("OPENAI_API_KEY")
        }
        self.settings = {}
        
        total_keys = sum(len(v) for v in self.keys.values())
        logger.info(f"[AI ROUTER] Initialized with {total_keys} total keys across providers.")

    def _parse_keys(self, env_var: str) -> List[str]:
        """Parses a comma-separated string of API keys into a clean list."""
        raw = os.environ.get(env_var, "")
        return [k.strip() for k in raw.split(",") if k.strip()]

    def update_config(self, settings: dict):
        """Injects dynamic settings from The Brain (Google Sheets)."""
        self.settings = settings

    def generate(self, prompt: str, require_json: bool = False) -> str:
        """
        Executes the prompt against available providers. 
        Implements intelligent fallback and token rotation logic.
        """
        # Primary: Anthropic (usually better at strict instruction following)
        # Fallback: OpenAI
        provider_order = ["anthropic", "openai"]
        
        for provider in provider_order:
            keys = self.keys.get(provider, [])
            
            while keys:
                current_key = keys[0]
                try:
                    if provider == "anthropic":
                        return self._call_anthropic(prompt, current_key, require_json)
                    elif provider == "openai":
                        return self._call_openai(prompt, current_key, require_json)
                        
                except requests.exceptions.HTTPError as e:
                    status_code = e.response.status_code
                    
                    if status_code == 401:
                        # FAIL-FAST: Unauthorized key. It's dead. Drop it permanently.
                        logger.warning(f"[AI ROUTER] 401 Unauthorized on {provider}. Purging dead key from rotation.")
                        keys.pop(0)
                        
                    elif status_code == 429:
                        # RATE LIMIT: Move the exhausted key to the back of the queue and pause briefly.
                        logger.warning(f"[AI ROUTER] 429 Rate Limit on {provider}. Rotating to next key.")
                        keys.append(keys.pop(0))
                        time.sleep(1.5) # Graceful backoff
                        
                    elif status_code >= 500:
                        # VENDOR OUTAGE: The provider is down. Skip to the next provider immediately.
                        logger.error(f"[AI ROUTER] 5xx Vendor Outage on {provider}. Switching providers.")
                        break 
                        
                    else:
                        logger.error(f"[AI ROUTER] Unexpected HTTP {status_code} from {provider}: {e.response.text}")
                        break
                        
                except Exception as e:
                    logger.error(f"[AI ROUTER] Unknown exception connecting to {provider}: {e}")
                    break # Abort this provider, try the next
                    
        # If the loop exhausts without returning, we are completely out of AI credits/keys.
        return "EXHAUSTED"

    def _call_anthropic(self, prompt: str, api_key: str, require_json: bool) -> str:
        """Executes API call to Anthropic Claude models."""
        url = "https://api.anthropic.com/v1/messages"
        headers = {
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json"
        }
        
        # Enforce JSON formatting instructions if required
        system_prompt = "You are a specialized corporate events data extractor."
        if require_json:
            system_prompt += " You must respond strictly with valid JSON. Do not include markdown formatting or commentary."
            
        payload = {
            "model": "claude-3-haiku-20240307", # Fast, cheap, capable model
            "system": system_prompt,
            "max_tokens": 1024,
            "messages": [{"role": "user", "content": prompt}]
        }
        
        response = requests.post(url, headers=headers, json=payload, timeout=15)
        response.raise_for_status()
        
        data = response.json()
        return data["content"][0]["text"]

    def _call_openai(self, prompt: str, api_key: str, require_json: bool) -> str:
        """Executes API call to OpenAI GPT models."""
        url = "https://api.openai.com/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": "gpt-4o-mini", # Fast, cheap, capable model
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.0 # Deterministic output
        }
        
        if require_json:
            payload["response_format"] = {"type": "json_object"}
            
        response = requests.post(url, headers=headers, json=payload, timeout=15)
        response.raise_for_status()
        
        data = response.json()
        return data["choices"][0]["message"]["content"]