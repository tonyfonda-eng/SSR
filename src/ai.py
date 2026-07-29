from openai import OpenAI
import os

api_key = os.environ.get("OPENAI_API_KEY")
client = OpenAI(api_key=api_key) if api_key else None

def classify_event(article_text, candidate_rules):
    """
    Given an article and a list of candidate rules (from rules_engine),
    ask the AI to determine the true intent and classify it into exactly one Event Family.
    """
    events = [r.get('Event Family') for r in candidate_rules]
    events_str = ', '.join(events)
    
    if not client:
        print("[WARNING] OPENAI_API_KEY not set. Mocking AI classification.")
        return events[0] if events else "Unknown"

    prompt = f"""
You are an expert event-driven investing analyst.

We have detected strong evidence that this article relates to one of the following Cash Events:
{events_str}

Article:
{article_text[:4000]}

Based on the intent of the article, which exact Cash Event from the list above is this? 
Return ONLY the exact name of the Event Family.
"""
    try:
        response = client.responses.create(
            model="gpt-5",
            input=prompt,
        )
        return response.output_text.strip()
    except Exception as e:
        print(f"[AI ERROR] {e}")
        return events[0] if events else "Unknown"


def execute_playbook(article_text, playbook_steps):
    """
    Given the playbook research questions, ask the AI to extract answers from the article.
    """
    if not client:
        return "[MOCK AI] OPENAI_API_KEY not set. AI Research skipped."

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
        response = client.responses.create(
            model="gpt-5",
            input=prompt,
        )
        return response.output_text.strip()
    except Exception as e:
        print(f"[AI ERROR] {e}")
        return f"[AI ERROR] {e}"
