"""
SSR 2.0: AI Core Inference Module
Decouples LLM interactions into three strict layers:
1. Provider Output (Raw text retrieval)
2. Structural Parser (Key/value validation)
3. Semantic Interpretation (Mapping to domain strategy)
"""
import json
import logging
import re
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
    rationale: str = ""

@dataclass
class TransactionNode:
    name: str
    ticker: str | None
    is_public: bool
    role: str
    extraction_confidence: float
    role_confidence: float

@dataclass
class TransactionEdge:
    source_node: str
    target_node: str
    relationship: str
    relationship_confidence: float

@dataclass
class TransactionGraph:
    nodes: list[TransactionNode]
    edges: list[TransactionEdge]
    error: str | None = None

    @property
    def entities(self) -> list[TransactionNode]:
        """Backward compatibility alias for nodes."""
        return self.nodes

# Backward compatibility alias
EntityRole = TransactionNode
ParsedEntities = TransactionGraph

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


def invoke_llm(prompt: str, json_mode: bool = False, router=None, prompt_type: str = "Unknown") -> str:
    """
    Retrieves the raw, unmodified string response from the AI provider.
    """
    if router is None:
        router = get_router()
    try:
        response = router.generate(prompt, require_json=json_mode, prompt_type=prompt_type)
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
        # Support both legacy schema (Event_Family) and new Google Sheets schema (classification)
        strategy = str(data.get("classification", data.get("Event_Family", "Unknown"))).strip()
        rationale = str(data.get("rationale", ""))
        evidence = data.get("Evidence", [])
        if not evidence and rationale:
            evidence = [rationale]
            
        return ParsedAIPayload(
            ticker=str(data.get("Ticker", "UNKNOWN")).strip().upper(),
            strategy=strategy,
            confidence_score=float(data.get("Confidence", 100.0)) / 100.0,
            raw_evidence=evidence,
            rationale=rationale
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

def extract_entities_and_roles(body_text: str, router=None) -> TransactionGraph:
    """
    Extracts the Transaction Graph: all mentioned organisations (Nodes) and their multi-node 
    relationships (Edges), explicitly assigning roles with dual confidence scores.
    """
    prompt = f"""Analyze this corporate text and build a Transaction Graph of ALL organisations mentioned and their relationships.

    Nodes represent organisations:
    - Roles: 'acquirer', 'target', 'seller', 'adviser', 'financing', 'competitor', 'supplier', 'shareholder', 'holding company', 'issuer'
    - 'is_public': boolean
    - 'ticker': uppercase symbol or null if private/unknown
    - 'extraction_confidence': float (0.0 to 1.0)
    - 'role_confidence': float (0.0 to 1.0)

    Edges represent relationships between nodes:
    - 'source_node': name of source organisation
    - 'target_node': name of target organisation
    - 'relationship': e.g., 'acquiring', 'selling_to', 'advising', 'funding', 'competing_with'
    - 'relationship_confidence': float (0.0 to 1.0)

    Text: {body_text[:4000]}

    Respond STRICTLY in this JSON format (no extra text):
    {{
        "nodes": [
            {{"name": "Company A", "ticker": "XYZ", "is_public": true, "role": "acquirer", "extraction_confidence": 0.99, "role_confidence": 0.93}},
            {{"name": "Company B", "ticker": null, "is_public": false, "role": "target", "extraction_confidence": 0.99, "role_confidence": 0.95}}
        ],
        "edges": [
            {{"source_node": "Company A", "target_node": "Company B", "relationship": "acquiring", "relationship_confidence": 0.95}}
        ]
    }}"""

    raw_output = invoke_llm(prompt, json_mode=True, router=router, prompt_type="Entity Extraction")

    if raw_output == "EXHAUSTED":
        return TransactionGraph(nodes=[], edges=[], error="EXHAUSTED")

    try:
        cleaned_output = raw_output.strip()
        if cleaned_output.startswith("```"):
            cleaned_output = re.sub(r"^```(?:json)?\n?", "", cleaned_output)
            cleaned_output = re.sub(r"\n?```$", "", cleaned_output)

        data = json.loads(cleaned_output)
        
        # Support fallback if model returned "entities" instead of "nodes"
        raw_nodes = data.get("nodes") or data.get("entities") or []
        nodes_list = []
        for e in raw_nodes:
            ticker_val = e.get("ticker")
            nodes_list.append(TransactionNode(
                name=e.get("name", "Unknown"),
                ticker=str(ticker_val).upper().replace('$', '') if ticker_val and str(ticker_val).upper() not in ["NONE", "NULL", "NONE/UNKNOWN", "UNKNOWN"] else None,
                is_public=bool(e.get("is_public", False)),
                role=e.get("role", "unknown"),
                extraction_confidence=float(e.get("extraction_confidence", 0.0)),
                role_confidence=float(e.get("role_confidence", 0.0))
            ))

        raw_edges = data.get("edges") or []
        edges_list = []
        for ed in raw_edges:
            edges_list.append(TransactionEdge(
                source_node=ed.get("source_node", ""),
                target_node=ed.get("target_node", ""),
                relationship=ed.get("relationship", "unknown"),
                relationship_confidence=float(ed.get("relationship_confidence", 0.0))
            ))

        return TransactionGraph(
            nodes=nodes_list,
            edges=edges_list,
            error=None
        )
    except json.JSONDecodeError:
        logger.warning("[AI CORE] Failed to parse entity extraction output as JSON.")
        return TransactionGraph(nodes=[], edges=[], error="Parse Failure")
    except Exception as e:
        logger.error(f"[AI CORE] Entity parsing exception: {e}")
        return TransactionGraph(nodes=[], edges=[], error="Parse Exception")


def extract_target_ticker(body_text: str, router=None) -> str:
    """Legacy wrapper for ticker extraction."""
    prompt = f"""Identify the primary ticker symbol for the company involved in this text. 
    Return ONLY the ticker symbol (e.g., AAPL). If multiple exist, return the primary subject. 
    If the company is private, return 'PRIVATE'. If no ticker is found, return 'UNKNOWN'.
    
    Text: {body_text[:4000]}"""
    
    raw_output = invoke_llm(prompt, json_mode=False, router=router, prompt_type="Ticker Extraction")
    return parse_ticker_output(raw_output)


def extract_halt_date(body_text: str, router=None) -> str:
    """Legacy wrapper for trading halt date extraction."""
    prompt = f"""Analyze the following press release regarding a resumption of trading.
    Identify the date when the original trading halt was enacted.
    Respond ONLY with the date in YYYY-MM-DD format. If not found, respond with "NOT FOUND".
    
    Text: {body_text[:4000]}"""
    
    raw_output = invoke_llm(prompt, json_mode=False, router=router, prompt_type="Halt Date Extraction")
    return parse_halt_date_output(raw_output)


def classify_event(body_text: str, matches: list, ticker: str = None, market_cap: float = None, router=None) -> str:
    """
    Legacy wrapper for event classification.
    Note: Returns a dict or strategy string depending on caller needs.
    """
    match_context = json.dumps([{"Rule": m["Rule"], "Summary": m["Summary"]} for m in matches])
    
    context_str = f"Target Ticker: {ticker}\n" if ticker else ""
    if market_cap:
         context_str += f"Target Market Cap: ${market_cap:,.2f}\n"

    # Try to load dynamic prompt from Google Sheets
    dynamic_prompt = None
    try:
        from src.sheets import load_ai_configurations
        from src.config.settings import SHEET_URL
        configs = load_ai_configurations(SHEET_URL)
        for cfg in configs:
            if cfg.get("Prompt ID") == "CLASSIFY_EVENT_V1":
                template = cfg.get("System Prompt Template", "")
                schema = cfg.get("Output JSON Schema", "")
                if template:
                    dynamic_prompt = template.replace("{context_str}", context_str).replace("{match_context}", match_context).replace("{body_text}", body_text[:6000])
                    dynamic_prompt += f"\n\nRespond in JSON format:\n{schema}"
                    break
    except Exception as e:
        logger.warning(f"Failed to load dynamic prompt: {e}")
        
    if dynamic_prompt:
        prompt = dynamic_prompt
    else:
        # Fallback to hardcoded prompt
        prompt = f"""Analyze this corporate text and the associated rule triggers.
        Categorize the event into EXACTLY ONE of these families:
        - Merger
        - Acquisition
        - Spin-off
        - Tender
        - Joint Venture
        - Restructuring
        - Distressed Sale
        - Asset Purchase
        - Take-private
        - Minority Investment
        - Strategic Partnership
        - Resumption of Trading
        - Unknown
        - False Positive
        
        {context_str}
        Rule Triggers: {match_context}
        
        Text: {body_text[:6000]}
        
        Respond in JSON format:
        {{
            "classification": "Category Name",
            "rationale": "Explanation"
        }}"""

    raw_output = invoke_llm(prompt, json_mode=True, router=router, prompt_type="Event Classification")
    parsed_payload = parse_classification_output(raw_output)
    
    # Return a dict to allow access to rationale by the V4 pipeline
    return {
        "status": "OK",
        "classification": parsed_payload.strategy,
        "rationale": parsed_payload.rationale,
        "confidence": parsed_payload.confidence_score
    }


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

    raw_output = invoke_llm(prompt, json_mode=False, router=router, prompt_type="Playbook Execution")
    
    if raw_output == "EXHAUSTED":
         return "FAILED: AI Providers Exhausted."
         
    return raw_output