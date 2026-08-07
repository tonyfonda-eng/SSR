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
        self.telemetry = []
        self.events = []
        
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

    def update_config(self, settings: list):
        """Injects dynamic settings from The Brain (Google Sheets)."""
        self.settings = {}
        if isinstance(settings, list):
            for item in settings:
                if isinstance(item, dict) and "Setting Name" in item:
                    self.settings[item["Setting Name"]] = item.get("Value")
        elif isinstance(settings, dict):
            self.settings = settings
        
    def get_telemetry(self) -> List[Dict]:
        """Returns the accumulated telemetry for this run."""
        return self.telemetry

    def get_events(self) -> List[Dict]:
        """Returns the accumulated black-box events for this run."""
        return self.events

    def generate(self, prompt: str, require_json: bool = False, prompt_type: str = "Unknown") -> str:
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
                    start_time = time.time()
                    latency_ms = 0
                    tokens_in = 0
                    tokens_out = 0
                    success = False
                    output = ""
                    
                    configured_model = self.settings.get("Default AI Model", "Gemini-1.5-Pro")
                    
                    if provider == "gemini":
                        output, tokens_in, tokens_out = self._call_gemini(prompt, current_key, require_json, configured_model)
                    elif provider == "openrouter":
                        output, tokens_in, tokens_out = self._call_openrouter(prompt, current_key, require_json, configured_model)
                        
                    latency_ms = int((time.time() - start_time) * 1000)
                    success = True
                    
                    self.telemetry.append({
                        "provider": provider,
                        "prompt_type": prompt_type,
                        "input_tokens": tokens_in,
                        "output_tokens": tokens_out,
                        "latency_ms": latency_ms,
                        "cost": (tokens_in * 0.075 / 1000000) + (tokens_out * 0.30 / 1000000) if provider == "gemini" else 0.0,
                        "success": True
                    })
                    
                    return output
                        
                except requests.exceptions.HTTPError as e:
                    latency_ms = int((time.time() - start_time) * 1000)
                    self.telemetry.append({
                        "provider": provider,
                        "prompt_type": prompt_type,
                        "input_tokens": 0, "output_tokens": 0, "latency_ms": latency_ms, "cost": 0, "success": False
                    })
                    status_code = getattr(e.response, 'status_code', 500)
                    
                    if status_code == 401 or status_code == 403:
                        # FAIL-FAST: Unauthorized key. It's dead. Drop it permanently.
                        logger.warning(f"[AI ROUTER] {status_code} on {provider}. Purging dead key from rotation.")
                        self.events.append({"source_or_provider": provider, "event_type": "401_UNAUTHORIZED", "severity": "CRITICAL", "details": "Key purged from rotation"})
                        with self._lock:
                            keys_ref = self.keys.get(provider, [])
                            if keys_ref and keys_ref[0] == current_key:
                                keys_ref.pop(0)
                        
                    elif status_code == 429:
                        # RATE LIMIT: Move the exhausted key to the back of the queue and pause briefly.
                        logger.warning(f"[AI ROUTER] 429 Rate Limit on {provider}. Rotating to next key.")
                        self.events.append({"source_or_provider": provider, "event_type": "429_RATE_LIMIT", "severity": "WARN", "details": f"Latency: {latency_ms}ms. Prompt: {prompt_type}"})
                        with self._lock:
                            keys_ref = self.keys.get(provider, [])
                            if keys_ref and keys_ref[0] == current_key:
                                keys_ref.append(keys_ref.pop(0))
                        time.sleep(1.5) # Graceful backoff
                        
                    elif status_code >= 500:
                        # VENDOR OUTAGE: The provider is down. Skip to the next provider immediately.
                        logger.error(f"[AI ROUTER] 5xx Vendor Outage on {provider}. Switching providers.")
                        self.events.append({"source_or_provider": provider, "event_type": f"{status_code}_VENDOR_OUTAGE", "severity": "CRITICAL", "details": "Switching providers"})
                        break 
                        
                    else:
                        logger.error(f"[AI ROUTER] Unexpected HTTP {status_code} from {provider}: {e}. (Model misconfigured?)")
                        self.events.append({"source_or_provider": provider, "event_type": f"HTTP_{status_code}", "severity": "CRITICAL", "details": str(e)})
                        break
                        
                except Exception as e:
                    logger.error(f"[AI ROUTER] Unknown exception connecting to {provider}: {e}")
                    self.events.append({"source_or_provider": provider, "event_type": "TIMEOUT_OR_NETWORK", "severity": "WARN", "details": str(e)})
                    break # Abort this provider, try the next
                    
        # If the loop exhausts without returning, we are completely out of AI credits/keys.
        self.events.append({"source_or_provider": "SYSTEM", "event_type": "AI_EXHAUSTED", "severity": "CRITICAL", "details": "All providers failed or exhausted."})
        return "EXHAUSTED"

    def _call_gemini(self, prompt: str, api_key: str, require_json: bool, configured_model: str) -> str:
        """Executes API call to Google Gemini REST API."""
        model_map = {
            "gemini-1.5-pro": "gemini-1.5-pro-latest",
            "gemini-1.5-flash": "gemini-1.5-flash-latest"
        }
        api_model = model_map.get(configured_model.lower(), "gemini-1.5-pro-latest")
        
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{api_model}:generateContent?key={api_key}"
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
            content = data["candidates"][0]["content"]["parts"][0]["text"]
            usage = data.get("usageMetadata", {})
            tokens_in = usage.get("promptTokenCount", 0)
            tokens_out = usage.get("candidatesTokenCount", 0)
            return content, tokens_in, tokens_out
        except (KeyError, IndexError):
            logger.error(f"[AI ROUTER] Unexpected Gemini response format: {data}")
            raise requests.exceptions.HTTPError(response=response)

    def _call_openrouter(self, prompt: str, api_key: str, require_json: bool, configured_model: str) -> str:
        """Executes API call to OpenRouter."""
        url = "https://openrouter.ai/api/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/tonyfonda-eng/SSR",
            "X-Title": "Special Situations Radar"
        }
        
        model_map = {
            "gemini-1.5-pro": "google/gemini-1.5-pro",
            "gemini-1.5-flash": "google/gemini-1.5-flash"
        }
        api_model = model_map.get(configured_model.lower(), "google/gemini-1.5-pro")
        
        system_prompt = "You are a specialized corporate events data extractor."
        if require_json:
            system_prompt += " You must respond strictly with valid JSON. Do not include markdown formatting or commentary."
            
        payload = {
            "model": api_model, 
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
        usage = data.get("usage", {})
        tokens_in = usage.get("prompt_tokens", 0)
        tokens_out = usage.get("completion_tokens", 0)
        
        return data["choices"][0]["message"]["content"], tokens_in, tokens_out
