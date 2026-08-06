"""
SSR 2.0: AI Core Inference Module
Decouples LLM interactions into three strict layers:
1. Provider Output (Raw text retrieval)
2. Structural Parser (Key/value validation)
3. Semantic Interpretation (Mapping to domain strategy)
"""
import json
import logging
from dataclasses import dataclass
from typing import Dict, Any, Tuple
from src.providers.router import ProviderRouter
from src.sheets import get_system_settings
from src.config.settings import SHEET_URL

logger = logging.getLogger(__name__)


# --- Domain Data Structures ---

@dataclass
class ParsedAIPayload:
    """Layer 2: Structural parsed data from the LLM."""
    ticker: str
    strategy: str
    confidence_score: float
    raw_evidence: list

@dataclass
class SemanticInterpretation:
    """Layer 3: Internal domain interpretation."""
    outcome: str  # "DETECTED", "DROPPED", "ARCHIVED"
    reason: str
    mapped_strategy: str


# --- Core Provider Layer (Layer 1) ---

def get_router():
    """Initializes the AI provider router with live configuration."""
    settings = get_system_settings(SHEET_URL)
    router = ProviderRouter()
    router.update_config(settings)
    return router


def invoke_llm(prompt: str, json_mode: bool = False, router=None) -> str:
    """
    Retrieves the raw, unmodified string response from the AI provider.
    """
    if router is None:
        router = get_router()
    try:
        response = router.generate(prompt, require_json=json_mode)
        if response == "EXHAUSTED":
            logger.critical("[AI CORE] Provider router exhausted all available keys.")
        return response
    except Exception as e:
        logger.error(f"[AI CORE] LLM Invocation failed: {e}")
        return "EXHAUSTED"


# --- Parsing Layer (Layer 2) ---

def parse_classification_output(raw_json_str: str) -> ParsedAIPayload:
    """
    Extracts structural keys from the raw JSON output.
    Does not evaluate business logic.
    """
    if raw_json_str == "EXHAUSTED":
        return ParsedAIPayload("EXHAUSTED", "EXHAUSTED", 0.0, [])
        
    try:
        data = json.loads(raw_json_str)
        return ParsedAIPayload(
            ticker=str(data.get("Ticker", "UNKNOWN")).strip().upper(),
            strategy=str(data.get("Event_Family", "Unknown")).strip(),
            confidence_score=float(data.get("Confidence", 50.0)) / 100.0,
            raw_evidence=data.get("Evidence", [])
        )
    except json.JSONDecodeError:
        logger.warning("[AI CORE] Failed to parse LLM output as JSON.")
        return ParsedAIPayload("ERROR", "Parse Failure", 0.0, [])
    except Exception as e:
        logger.error(f"[AI CORE] Structural parsing exception: {e}")
        return ParsedAIPayload("ERROR", "Parse Exception", 0.0, [])


def parse_ticker_output(raw_str: str) -> str:
    """Extracts just the ticker string from a raw response."""
    if raw_str == "EXHAUSTED":
        return "EXHAUSTED"
    return raw_str.strip().upper().replace("$", "").split()[0] if raw_str else "UNKNOWN"


def parse_halt_date_output(raw_str: str) -> str:
    """Extracts a YYYY-MM-DD date string."""
    if not raw_str or "NOT FOUND" in raw_str.upper():
        return ""
    return raw_str.strip()


# --- Interpretation Layer (Layer 3) ---

def interpret_strategy(parsed_data: ParsedAIPayload) -> SemanticInterpretation:
    """
    Evaluates the parsed structural data against internal business rules
    to determine the final system action and justification.
    """
    if parsed_data.strategy == "EXHAUSTED":
        return SemanticInterpretation("DROPPED", "AI Providers Exhausted", "None")
        
    strategy_lower = parsed_data.strategy.lower()
    
    if "false positive" in strategy_lower:
        return SemanticInterpretation("DROPPED", "AI Assessed False Positive", "False Positive")
        
    if strategy_lower == "unknown" or parsed_data.strategy == "":
        return SemanticInterpretation("ARCHIVED", "Unknown Event Family", "Unknown")
        
    return SemanticInterpretation("DETECTED", "High Confidence Classification", parsed_data.strategy)


# ---------------------------------------------------------------------------
# Legacy Wrapper Functions (Backward Compatibility for `monitor.py`)
# ---------------------------------------------------------------------------

def extract_target_ticker(body_text: str, router=None) -> str:
    """Legacy wrapper for ticker extraction."""
    prompt = f"""Identify the primary ticker symbol for the company involved in this text. 
    Return ONLY the ticker symbol (e.g., AAPL). If multiple exist, return the primary subject. 
    If the company is private, return 'PRIVATE'. If no ticker is found, return 'UNKNOWN'.
    
    Text: {body_text[:4000]}"""
    
    raw_output = invoke_llm(prompt, json_mode=False, router=router)
    return parse_ticker_output(raw_output)


def extract_halt_date(body_text: str, router=None) -> str:
    """Legacy wrapper for trading halt date extraction."""
    prompt = f"""Analyze the following press release regarding a resumption of trading.
    Identify the date when the original trading halt was enacted.
    Respond ONLY with the date in YYYY-MM-DD format. If not found, respond with "NOT FOUND".
    
    Text: {body_text[:4000]}"""
    
    raw_output = invoke_llm(prompt, json_mode=False, router=router)
    return parse_halt_date_output(raw_output)


def classify_event(body_text: str, matches: list, ticker: str = None, market_cap: float = None, router=None) -> str:
    """
    Legacy wrapper for event classification.
    Note: Returns the strategy string directly to support legacy caller signatures.
    To utilize the full decoupled payload, the caller should implement Layer 1-3 manually.
    """
    match_context = json.dumps([{"Rule": m["Rule"], "Summary": m["Summary"]} for m in matches])
    
    context_str = f"Target Ticker: {ticker}\n" if ticker else ""
    if market_cap:
         context_str += f"Target Market Cap: ${market_cap:,.2f}\n"

    prompt = f"""Analyze this corporate text and the associated rule triggers.
    Categorize the event into EXACTLY ONE of these families:
    - Cash Merger
    - Resumption of Trading
    - M&A Naked Call Strategy
    - Unknown
    - False Positive
    
    {context_str}
    Rule Triggers: {match_context}
    
    Text: {body_text[:6000]}
    
    Respond in JSON format:
    {{
        "Ticker": "XYZ",
        "Event_Family": "Category Name",
        "Confidence": 95,
        "Evidence": ["List of key phrases supporting conclusion"]
    }}"""

    raw_output = invoke_llm(prompt, json_mode=True, router=router)
    parsed_payload = parse_classification_output(raw_output)
    
    # We return just the strategy string here to satisfy the legacy signature in monitor.py
    # monitor.py handles the interpretation layer logic.
    return parsed_payload.strategy


def execute_playbook(body_text: str, playbook_steps: str, event_family: str, gold_standard: str = None, market_data_str: str = "", router=None) -> str:
    """Executes a specific investment research playbook."""
    if not playbook_steps:
        return "No specific playbook instructions provided for this event family."
        
    gs_context = f"\nUse this as an example of an excellent summary:\n{gold_standard}\n" if gold_standard else ""
    
    prompt = f"""You are a quantitative hedge fund analyst specializing in {event_family}.
    Read the following corporate announcement and execute the research steps below.
    
    {market_data_str}
    
    Research Steps to Execute:
    {playbook_steps}
    {gs_context}
    
    Announcement Text:
    {body_text[:8000]}
    
    Provide your output as a professional investment memo."""

    raw_output = invoke_llm(prompt, json_mode=False, router=router)
    
    if raw_output == "EXHAUSTED":
         return "FAILED: AI Providers Exhausted."
         
    return raw_output