import os
import time
import logging

logger = logging.getLogger(__name__)

# Scraper classification tasks require efficient, short outputs to stay within free tier limits
MAX_TOKENS = 1024
COOLDOWN_SECONDS = 300  # 5-minute backoff on 402/rate-limit errors instead of permanent removal

class OpenRouterPool:
    def __init__(self):
        raw_keys = [os.environ.get("OPENROUTER_API_KEY", "")]
        for i in range(1, 8):
            raw_keys.append(os.environ.get(f"OPENROUTER_API_KEY_{i}", ""))
        
        # Filter out blank or whitespace-only keys
        self.keys = [k.strip() for k in raw_keys if k and k.strip()]
        self.cooldowns = {}  # key -> timestamp when it can be retried
        logger.info(f"[AI INFO] Initialized OpenRouter pool with {len(self.keys)} active keys.")

    def get_available_key(self):
        now = time.time()
        for key in self.keys:
            if self.cooldowns.get(key, 0) < now:
                return key
        return None  # All keys currently in cooldown

    def mark_cooldown(self, key):
        self.cooldowns[key] = time.time() + COOLDOWN_SECONDS
        logger.warning(f"[AI RETRY] OpenRouter key placed on cooldown for {COOLDOWN_SECONDS}s.")

class GeminiPool:
    def __init__(self):
        raw_keys = [os.environ.get("GEMINI_API_KEY", "")]
        for i in range(1, 8):
            raw_keys.append(os.environ.get(f"GEMINI_API_KEY_{i}", ""))
        
        # Filter out blank or whitespace-only keys to prevent ghost slots
        self.keys = [k.strip() for k in raw_keys if k and k.strip()]
        self._index = 0
        logger.info(f"[AI INFO] Initialized Gemini pool with {len(self.keys)} active keys.")

    def next_key(self):
        if not self.keys:
            return None
        # True round-robin load distribution via modulo indexing
        key = self.keys[self._index % len(self.keys)]
        self._index += 1
        return key

# Global singleton client pools
or_pool = OpenRouterPool()
gemini_pool = GeminiPool()
