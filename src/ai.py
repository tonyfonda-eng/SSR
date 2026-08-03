import os
import time
import logging
import requests
import re

logger = logging.getLogger(__name__)

MAX_TOKENS = 2048
COOLDOWN_SECONDS = 300

class OpenRouterPool:
    def __init__(self):
        raw_keys = []
        env_vars = ["OPENROUTER_API_KEY"] + [f"OPENROUTER_API_KEY_{i}" for i in range(1, 8)]
        for var in env_vars:
            val = os.environ.get(var, "")
            if val:
                raw_keys.extend([k.strip() for k in val.split(",") if k.strip()])
        
        self.keys = raw_keys
        self.cooldowns = {}
        logger.info(f"[AI INFO] OpenRouter keys parsed: {len(self.keys)}")

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
        logger.info(f"[AI INFO] Gemini keys parsed: {len(self.keys)}")

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
    """Shared retry generator bridging OpenRouter and Gemini key pools with cross-failover."""
    while True:
        key = or_pool.get_available_key()
        if key is None:
            break
        try:
            headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
            payload = {
                "model": "google/gemini-2.5-flash",
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

    # Secondary Failover: Native Google Gemini API Pool
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

    raise RuntimeError("All AI client pools exhausted completely.")

def extract_target_ticker(body: str) -> str:
    """Robust ticker extraction pattern handling case variations, wrappers, and suffixes."""
    if not body:
        return "UNKNOWN"
    
    # Heuristic 1: Standard Exchange prefix matching (e.g., NASDAQ: AAPL, lon:lseg)
    match = re.search(r'\b(?:NYSE|NASDAQ|LON|ASX|TSX):\s*([A-Z]{1,5})\b', body, re.IGNORECASE)
    if match:
        return match.group(1).upper()
        
    # Heuristic 2: Parentheses ticker formatting common in press releases (e.g., "(Ticker: BHP)")
    match = re.search(r'\((?:Symbol|Ticker|NYSE|NASDAQ):\s*([A-Z]{1,5})\)', body, re.IGNORECASE)
    if match:
        return match.group(1).upper()

    # Heuristic 3: Bloomberg/Reuters style equity suffixes (e.g. RIO.AX, VOD.L)
    match = re.search(r'\b([A-Z]{1,5})\.(?:L|AX|TO|N|O)\b', body)
    if match:
        return match.group(1).upper()
        
    return "UNKNOWN"

def extract_halt_date(body: str) -> str:
    """Extracts date strings dynamically from corporate event text context."""
    if not body:
        return datetime.date.today().isoformat()
    
    # Scan for common date formats near keyword contexts (e.g., "halted on 2026-08-01")
    date_match = re.search(r'\b(\d{4})[-/](\d{2})[-/](\d{2})\b', body)
    if date_match:
        return f"{date_match.group(1)}-{date_match.group(2)}-{date_match.group(3)}"
        
    return datetime.date.today().isoformat()

def classify_event(body: str, matches: list, ticker: str = "UNKNOWN", market_cap: float = None) -> str:
    """Classifies incoming text streams into defined qualitative event categories."""
    try:
        prompt = (
            f"Analyze this financial corporate filing announcement text. "
            f"Classify it into an exclusive investment category (e.g. M&A Announcement, Spin-Off, Tender Offer, Asset Sale, Resumption of Trading).\n"
            f"Return ONLY the plain title text of the category. Text:\n\n{body[:1200]}"
        )
        return _generate_with_retry(prompt, max_tokens=60).strip()
    except Exception:
        if matches and len(matches) > 0:
            return matches[0].get("Name", "Unknown Event")
        return "Unknown"

def execute_playbook(body: str, playbook_steps: str, event_family: str, gold_standard: str = None, market_data_str: str = "") -> str:
    """
    FIXED SIGNATURE LAYER: Dynamically evaluates the filing against structural research playbooks.
    Generates the core situational analysis memo sent to your dispatch systems.
    """
    prompt = (
        f"### SYSTEM ROLE: ADVANCED INVESTOR SPECIAL SITUATIONS RESEARCH AI ###\n"
        f"Analyze this corporate development announcement for category: {event_family}.\n"
        f"Ticker Context: {market_data_str}\n\n"
        f"Follow these strict execution steps meticulously:\n{playbook_steps}\n\n"
    )
    
    if gold_standard:
        prompt += f"Align output structure with this gold standard model template:\n{gold_standard}\n\n"
        
    prompt += f"Announcement Text Source Material:\n\n{body}"
    
    try:
        return _generate_with_retry(prompt, max_tokens=MAX_TOKENS)
    except Exception as e:
        return f"[ERROR] Playbook execution stalled or resource pools exhausted: {e}"