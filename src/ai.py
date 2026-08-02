import os
import time
import logging
import requests

logger = logging.getLogger(__name__)

MAX_TOKENS = 1024
COOLDOWN_SECONDS = 300

class OpenRouterPool:
    def __init__(self):
        raw_keys = []
        # Pull master keys and numbered fallback variables
        env_vars = ["OPENROUTER_API_KEY"] + [f"OPENROUTER_API_KEY_{i}" for i in range(1, 8)]
        for var in env_vars:
            val = os.environ.get(var, "")
            if val:
                # Split on commas to unpack bulk GitHub secrets cleanly
                raw_keys.extend([k.strip() for k in val.split(",") if k.strip()])
        
        self.keys = raw_keys
        self.cooldowns = {}
        print(f"\n======== AI POOL ========\nOpenRouter keys loaded: {len(self.keys)}")
        for i, k in enumerate(self.keys):
            print(f"  OpenRouter {i+1}: {k[:8]}...{k[-4:]}")
        logger.info(f"[AI INFO] Initialized OpenRouter pool with {len(self.keys)} active keys.")

    def get_available_key(self):
        now = time.time()
        for key in self.keys:
            if self.cooldowns.get(key, 0) < now:
                return key
        return None

    def mark_cooldown(self, key):
        self.cooldowns[key] = time.time() + COOLDOWN_SECONDS
        logger.warning(f"[AI RETRY] OpenRouter key placed on cooldown for {COOLDOWN_SECONDS}s.")

class GeminiPool:
    def __init__(self):
        raw_keys = []
        env_vars = ["GEMINI_API_KEY"] + [f"GEMINI_API_KEY_{i}" for i in range(1, 8)]
        for var in env_vars:
            val = os.environ.get(var, "")
            if val:
                raw_keys.extend([k.strip() for k in val.split(",") if k.strip()])
        
        self.keys = raw_keys
        self._index = 0
        print(f"Gemini keys loaded: {len(self.keys)}")
        for i, k in enumerate(self.keys):
            print(f"  Gemini {i+1}: {k[:8]}...{k[-4:]}")
        logger.info(f"[AI INFO] Initialized Gemini pool with {len(self.keys)} active keys.\n")

    def next_key(self):
        if not self.keys:
            return None
        key = self.keys[self._index % len(self.keys)]
        self._index += 1
        return key

or_pool = OpenRouterPool()
gemini_pool = GeminiPool()
clients = or_pool.keys

def _generate_with_retry(prompt: str, max_tokens: int = MAX_TOKENS) -> str:
    """Shared retry generator bridging OpenRouter and Gemini key pools."""
    while True:
        key = or_pool.get_available_key()
        if key is None:
            break
        try:
            headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
            payload = {
                "model": "google/gemini-2.0-flash-exp:free",
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": max_tokens
            }
            resp = requests.post("https://openrouter.ai/api/v1/chat/completions", json=payload, headers=headers, timeout=30)
            if resp.status_code in (402, 429):
                or_pool.mark_cooldown(key)
                continue
            resp.raise_for_status()
            data = resp.json()
            return data["choices"][0]["message"]["content"]
        except Exception as e:
            logger.warning(f"[AI WARNING] OpenRouter key error encountered: {e}. Moving to next key.")
            or_pool.mark_cooldown(key)
            continue

    for _ in range(len(gemini_pool.keys)):
        key = gemini_pool.next_key()
        if not key:
            break
        try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={key}"
            payload = {"contents": [{"parts": [{"text": prompt}]}]}
            resp = requests.post(url, json=payload, timeout=30)
            if resp.status_code == 429:
                continue
            resp.raise_for_status()
            data = resp.json()
            return data["candidates"][0]["content"]["parts"][0]["text"]
        except Exception:
            continue

    raise RuntimeError("All AI clients exhausted")

def extract_target_ticker(body: str) -> str:
    import re
    match = re.search(r'\b(?:NYSE|NASDAQ|LON|ASX|TSX):\s*([A-Z]{1,5})\b', body)
    if match:
        return match.group(1)
    return "UNKNOWN"

def extract_halt_date(body: str) -> str:
    return "2026-01-01"

def classify_event(body: str, matches: list, ticker: str = "UNKNOWN", market_cap: float = None) -> str:
    try:
        prompt = f"Classify this corporate action event into a short category name:\n\n{body[:1500]}"
        return _generate_with_retry(prompt, max_tokens=100).strip()
    except Exception:
        if matches and len(matches) > 0:
            return matches[0].get("Name", "Unknown Event")
        return "Unknown"

def execute_playbook(event_family: str, ticker: str, market_data: str) -> str:
    return f"Executed playbook for {event_family} on {ticker}"
