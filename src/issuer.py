"""
SSR 2.0: Entity Resolution Node (Issuer Identification)
Utilizes the Layer 1 Provider Output abstraction to extract the canonical 
corporate entity from a sensor's raw text payload.
"""
import logging
from src.ai import invoke_llm

logger = logging.getLogger(__name__)

def extract_issuing_company(source_name: str, title: str, body: str) -> str:
    """
    Evaluates the raw article text to extract the primary issuing company.
    Returns the exact string name, 'UNKNOWN', or 'EXHAUSTED' for upstream handling.
    """
    if not title and not body:
        return "UNKNOWN"

    prompt = f"""You are a quantitative financial entity resolution engine.
    Analyze the following corporate press release and identify the PRIMARY issuing company.
    Respond ONLY with the exact company name. Do not include tickers, legal suffixes (like Inc. or Corp.) unless critical for disambiguation, and do not add any conversational text.
    If multiple companies are mentioned (e.g., in an M&A transaction), return the specific company that issued the release.
    If it is impossible to determine the issuer, respond EXACTLY with the word "UNKNOWN".

    Sensor Source: {source_name}
    Headline: {title}
    
    Raw Payload:
    {body[:4000]}
    """
    
    try:
        # Route through the unified SSR 2.0 AI Provider abstraction
        raw_response = invoke_llm(prompt, json_mode=False)
        
        if raw_response == "EXHAUSTED":
            return "EXHAUSTED"
            
        cleaned = raw_response.strip().replace('"', '').replace("'", "")
        
        if not cleaned or cleaned.upper() == "UNKNOWN":
            return "UNKNOWN"
            
        return cleaned
        
    except Exception as e:
        logger.error(f"[ENTITY RESOLUTION] Structural failure extracting issuer from {source_name}: {e}")
        return "UNKNOWN"