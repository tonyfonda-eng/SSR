import os
import random
from google import genai

raw_keys = os.environ.get("GEMINI_API_KEY", "")
api_keys = [k.strip() for k in raw_keys.split(",") if k.strip()]
clients = [genai.Client(api_key=k) for k in api_keys]

def _get_client():
    if not clients:
        return None
    return random.choice(clients)

def classify_event(article_text, candidate_rules):
    """
    Given an article and a list of candidate rules (from rules_engine),
    ask the AI to determine the true intent and classify it into exactly one Event Family.
    """
    events = [r.get('Event Family') for r in candidate_rules]
    events_str = ', '.join(events)
    
    # Extract custom training instructions from the Google Sheet
    instructions = []
    for r in candidate_rules:
        event = r.get('Event Family')
        ai_prompt = str(r.get('AI Prompt', '')).strip()
        if ai_prompt:
            instructions.append(f"- For '{event}': {ai_prompt}")
            
    custom_instructions_str = "\n".join(instructions)
    if custom_instructions_str:
        custom_instructions_str = f"\nHere are specific training instructions from the analyst:\n{custom_instructions_str}\n"
    
    client = _get_client()
    if not client:
        print("[WARNING] GEMINI_API_KEY not set. Mocking AI classification.")
        return events[0] if events else "Unknown"

    prompt = f"""
You are an expert event-driven investing analyst.

We have detected strong evidence that this article relates to one of the following Cash Events:
{events_str}
{custom_instructions_str}
Article:
{article_text[:4000]}

Based on the intent of the article, which exact Cash Event from the list above is this? 
If the article is a false positive and does NOT represent a real corporate cash event (such as marketing, generic advice, or product launches), return 'False Positive'.
Otherwise, return ONLY the exact name of the Event Family.
"""
    try:
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt,
        )
        return response.text.strip()
    except Exception as e:
        print(f"[AI ERROR] {e}")
        return events[0] if events else "Unknown"


def execute_playbook(article_text, playbook_steps):
    """
    Given the playbook research questions, ask the AI to extract answers from the article.
    """
    client = _get_client()
    if not client:
        return "[MOCK AI] GEMINI_API_KEY not set. AI Research skipped."

    prompt = f"""
You are an expert event-driven investing analyst executing a research playbook on a cash event.

Research Playbook:
{playbook_steps}

Article:
{article_text[:6000]}

Please extract the answers for the playbook steps based ONLY on the provided article.
Keep it extremely concise. 
If the information is not present in the article, state "Not disclosed in article".
"""
    try:
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt,
        )
        return response.text.strip()
    except Exception as e:
        print(f"[AI ERROR] {e}")
        return f"[AI ERROR] {e}"


def extract_target_ticker(article_text):
    """
    Given an article, ask the AI to identify the target company and return its stock ticker.
    """
    client = _get_client()
    if not client:
        return "[MOCK AI] GEMINI_API_KEY not set. Ticker Extraction skipped."

    prompt = f"""
You are an expert event-driven investing analyst. Read this article and identify the PRIMARY company that is the subject of this cash event (e.g. the company being acquired, delisted, or undergoing liquidation).

Article:
{article_text[:6000]}

If the primary subject company is publicly traded on a global stock exchange, return ONLY its primary ticker symbol. 
If it is an international stock, use the standard Yahoo Finance suffix (e.g., 'VOD.L' for London, '005930.KS' for Korea).
If the company is private, or if you cannot determine the ticker, return exactly 'PRIVATE'.
Return NOTHING ELSE besides the ticker or 'PRIVATE'.
"""
    try:
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt,
        )
        return response.text.strip().upper()
    except Exception as e:
        print(f"[AI ERROR] Ticker Extraction: {e}")
        return "UNKNOWN"
