import os
import random
from google import genai
import openai

# --- 1. Load Gemini Keys ---
raw_gemini_keys = os.environ.get("GEMINI_API_KEY", "")
gemini_keys = [k.strip() for k in raw_gemini_keys.split(",") if k.strip()]
for i in range(1, 11):
    val = os.environ.get(f"GEMINI_API_KEY_{i}")
    if val:
        keys = [k.strip() for k in val.split(",") if k.strip()]
        gemini_keys.extend(keys)
gemini_keys = list(set(gemini_keys))

# --- 2. Load OpenRouter Keys ---
raw_or_keys = os.environ.get("OPENROUTER_API_KEY", "")
or_keys = [k.strip() for k in raw_or_keys.split(",") if k.strip()]
for i in range(1, 11):
    val = os.environ.get(f"OPENROUTER_API_KEY_{i}")
    if val:
        keys = [k.strip() for k in val.split(",") if k.strip()]
        or_keys.extend(keys)
or_keys = list(set(or_keys))

# --- 3. Initialize Unified Client Pool ---
# Pool stores tuples: (provider_name, client_instance, masked_key)
clients = []

for idx, k in enumerate(or_keys):
    # OpenRouter uses the OpenAI SDK structure
    client = openai.Client(
        base_url="https://openrouter.ai/api/v1",
        api_key=k,
    )
    clients.append(("openrouter", client, f"OpenRouter-{idx+1:02d}"))

for idx, k in enumerate(gemini_keys):
    client = genai.Client(api_key=k)
    clients.append(("gemini", client, f"Gemini-{idx+1:02d}"))

print(f"[AI INFO] Initialized {len(or_keys)} OpenRouter clients and {len(gemini_keys)} Gemini clients.")

def _generate_with_retry(prompt, max_retries=3):
    if not clients:
        raise ValueError("No API keys (OpenRouter or Gemini) set in environment.")
    
    import time
    import re
    
    # We want to prioritize OpenRouter (since Llama 3.3 70B free has high limits) 
    # but still allow random distribution to avoid hitting same key constantly.
    available_clients = list(clients)
    
    # Sort so OpenRouter is tried first, but shuffle within providers
    or_clients = [c for c in available_clients if c[0] == "openrouter"]
    gem_clients = [c for c in available_clients if c[0] == "gemini"]
    random.shuffle(or_clients)
    random.shuffle(gem_clients)
    available_clients = or_clients + gem_clients
    
    last_error = None
    for attempt in range(max_retries):
        for client_tuple in list(available_clients):
            provider, client, masked_key = client_tuple
            start_t = time.perf_counter()
            is_retry = attempt > 0
            
            try:
                if provider == "openrouter":
                    response = client.chat.completions.create(
                        model="google/gemini-2.0-flash-001-001",
                        messages=[{"role": "user", "content": prompt}],
                        extra_body={
                            "models": [
                                "google/gemini-2.0-flash-001-001",
                                "google/gemini-2.0-flash-001-001",
                                "google/gemini-2.0-flash-001-001"
                            ]
                        }
                        
                    )
                    txt = response.choices[0].message.content.strip()
                    rt = time.perf_counter() - start_t
                    from src.monitoring import MetricsCollector
                    MetricsCollector.get_instance().log_ai_usage(provider, masked_key, True, response_time=rt, is_retry=is_retry, is_fallback=True)
                    return txt
                    
                elif provider == "gemini":
                    response = client.models.generate_content(
                        model='gemini-flash-latest',
                        contents=prompt,
                    )
                    txt = response.text.strip()
                    rt = time.perf_counter() - start_t
                    from src.monitoring import MetricsCollector
                    MetricsCollector.get_instance().log_ai_usage(provider, masked_key, True, response_time=rt, is_retry=is_retry)
                    return txt
                    
            except Exception as e:
                rt = time.perf_counter() - start_t
                last_error = e
                error_str = str(e)
                
                is_429 = "429" in error_str
                is_503 = "503" in error_str or "502" in error_str
                is_timeout = "timeout" in error_str.lower()
                
                from src.monitoring import MetricsCollector
                MetricsCollector.get_instance().log_ai_usage(provider, masked_key, False, is_429=is_429, is_503=is_503, is_timeout=is_timeout, is_retry=is_retry, response_time=rt)
                
                # Handle provider-specific rate limits and auth errors
                is_fatal_or = provider == "openrouter" and any(x in error_str for x in ["401", "404", "402", "400"])
                is_fatal_gemini = provider == "gemini" and "GenerateRequestsPerDay" in error_str
                
                if is_fatal_or:
                    print(f"[AI RETRY] OpenRouter key exhausted, invalid, or model unavailable. Removing from pool. Error: {error_str}")
                    if client_tuple in available_clients: available_clients.remove(client_tuple)
                    if client_tuple in clients: clients.remove(client_tuple)
                elif is_fatal_gemini:
                    print("[AI RETRY] Gemini key hit absolute daily quota. Removing from pool.")
                    if client_tuple in available_clients: available_clients.remove(client_tuple)
                    if client_tuple in clients: clients.remove(client_tuple)
                    
                if not available_clients:
                    raise ValueError("CRITICAL: All AI keys (OpenRouter and Gemini) have exhausted their quotas.")
                    
                continue # Swap to next key instantly
                    
        # If we reach here, we've looped through ALL available keys and they ALL failed for non-fatal reasons
        # Now we must sleep before trying the next cycle.
        wait_time = 20
        if last_error and provider == "gemini":
            match = re.search(r'retry in (\d+(?:\.\d+)?)s', str(last_error))
            if match:
                wait_time = min(float(match.group(1)) + 1, 60)
        
        print(f"[AI RETRY] Attempt {attempt+1} failed across all keys. Retrying in {wait_time:.1f}s...")
        time.sleep(wait_time)
        
    raise Exception(f"Failed to generate content after {max_retries} cycles. Last error: {last_error}")

def classify_event(article_text, candidate_rules, ticker='UNKNOWN', market_cap=None):
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
    
    if not clients:
        print("[WARNING] GEMINI_API_KEY not set. Mocking AI classification.")
        return events[0] if events else "Unknown"

    financial_context = f"Target Company: {ticker}\n"
    if market_cap:
        financial_context += f"Approximate Market Cap: ${market_cap:,.2f}\n"

    prompt = f"""
You are an expert event-driven investing analyst.

{financial_context}
We have detected strong evidence that this article relates to one of the following Cash Events:
{events_str}
{custom_instructions_str}
Article:
{article_text[:4000]}

Based on the intent of the article, which exact Cash Event from the list above is this? 
If the article is a false positive and does NOT represent a real corporate cash event, OR if it fails to meet any mathematical constraints defined in the instructions (e.g., settlement value relative to market cap), return 'False Positive'.
Otherwise, return ONLY the exact name of the Event Family.
"""
    try:
        return _generate_with_retry(prompt)
    except Exception as e:
        print(f"[AI ERROR] All keys exhausted or failed: {e}")
        error_msg = str(e).lower()
        if "exhausted" in error_msg or "no api keys" in error_msg:
            return "EXHAUSTED"
        return events[0] if events else "Unknown"


def execute_playbook(article_text, playbook_steps, event_family, gold_standard=None, market_data_str=""):
    """
    Acts as a 1st-year IB analyst executing a structured investment memo.
    """
    if not clients:
        return "[MOCK AI] GEMINI_API_KEY not set. AI Research skipped."

    gold_standard_str = ""
    if gold_standard:
        gold_standard_str = f"\n\n--- GOLD STANDARD ANALYST EXAMPLE ---\nHere is how a senior analyst at our firm wrote a highly praised memo for a similar event. Emulate the tone, brevity, and focus on mathematical upside seen here:\n{gold_standard}\n---------------------------------------\n"

    market_context = f"\n\n--- LIVE MARKET DATA (FOR YOUR CALCULATIONS) ---\n{market_data_str}\n------------------------------------------------\n" if market_data_str else ""

    prompt = f"""
You are a first-year investment banking analyst who has exactly 10 minutes to brief a portfolio manager.
You have been handed an article regarding a '{event_family}'.{gold_standard_str}{market_context}

The portfolio manager ONLY wants to know: "Is this potentially investable, and if so, why?"
Do NOT write a narrative summary of what happened. Extract only objective facts.
You MUST format your response EXACTLY using the markdown sections below. 

Note: "3. Why did SSR trigger?" is generated by the python backend. You will generate sections 1, 2, 4, 5, 6, 7, 8, 9, 10, the Checklist, and the To-Do list.

1. Executive Summary
Maximum 5 lines. Example: Cash acquisition announced. ABC Corp has agreed to acquire XYZ plc for £18.25/share in cash. Premium approximately 31%. Expected completion Q1 2027. Initial review recommended.

2. Event Classification
Structured fields only: Event Family, Subtype, Status, Target, Acquirer, Jurisdiction, Country, Exchange, Language.

4. Investment Facts & Returns
Extract ONLY objective facts. Do NOT use prose. Use fields like: Offer price, Undisturbed price, Premium %, Expected completion, Board recommendation, Break fee.
CRITICAL MATH: If an Offer Price and a current market price are available, explicitly calculate the 'Gross Spread (%)'. If an expected closing date is available, explicitly calculate the 'Estimated Annualized IRR'.
(Also incorporate these specific research questions if relevant: {playbook_steps})

5. Risk Assessment
Explain the risks. Primary risks (e.g. Competition authority approval, Financing). Unknowns (e.g. Break fee not disclosed).

6. Market Context
Has another bidder appeared? Strategic buyer? Hostile? Insider ownership?

7. Trading Relevance
Would merger arbitrage funds care? Liquidity, Market cap, Borrow concerns, Likely arbitrage candidate.

8. Missing Information
Explicitly state what you DO NOT KNOW from the article (e.g. Financing banks, Dissent rights, Regulatory filing date).

9. Suggested Next Reading
What SEC or regulatory documents should the analyst read next?

10. AI Opinion
Maximum 3 sentences. Only here can you express an opinion on complexity and standard red flags.
NEVER provide price targets, DCFs, Buy/Sell recommendations, fair value, predict success, predict stock performance, or macro commentary.

11. Checklist Table
Create a markdown table with exactly two columns (Question, Answer).
Questions must include: Public target?, Cash event?, Actionable?, Premium disclosed?, Financing disclosed?, Board support?, Immediate review required?

12. Analyst To-Do List
A bulleted list of 3-5 remaining diligence tasks.

Article text:
{article_text[:6000]}
"""
    try:
        return _generate_with_retry(prompt)
    except Exception as e:
        print(f"[AI ERROR] All keys exhausted or failed: {e}")
        error_msg = str(e).lower()
        if "exhausted" in error_msg or "no api keys" in error_msg:
            return "EXHAUSTED"
        return f"[AI ERROR] {e}"


def extract_target_ticker(article_text):
    """
    Given an article, ask the AI to identify the target company and return its stock ticker.
    """
    if not clients:
        return "[MOCK AI] GEMINI_API_KEY not set. Ticker Extraction skipped."

    prompt = f"""
You are an expert event-driven investing analyst. Read this article and identify the PRIMARY company that is the subject of this cash event (e.g. the company being acquired, delisted, or undergoing liquidation).

Article:
{article_text[:6000]}

If the primary subject company is publicly traded on a global stock exchange, return ONLY its primary ticker symbol. 
If it is an international stock, use the standard Yahoo Finance suffix (e.g., 'VOD.L' for London, '005930.KS' for Korea).
If the primary subject company is a PRIVATE company (e.g. it is not traded on any stock exchange), return exactly the word 'PRIVATE'.
If you cannot determine the ticker or public/private status, return ONLY the company's clean, formal name (e.g., 'LECTRA', 'VANTIVA', 'SPACE X'). 
Return NOTHING ELSE besides the ticker, the word 'PRIVATE', or the company name. Do NOT return 'UNKNOWN'.
"""
    try:
        text = _generate_with_retry(prompt)
        return text.upper()
    except Exception as e:
        print(f"[AI ERROR] Ticker Extraction failed: {e}")
        error_msg = str(e).lower()
        if "exhausted" in error_msg or "no api keys" in error_msg:
            return "EXHAUSTED"
        return "UNKNOWN"

def extract_halt_date(article_text):
    """
    Extracts the original trading halt date from a resumption article.
    """
    if not clients:
        return None

    prompt = f"""
You are an analyst reviewing a press release about a stock resuming trading after a halt.
When did the original trading halt begin?

Article:
{article_text[:6000]}

Return ONLY the date in YYYY-MM-DD format. If you cannot determine the date, return exactly 'UNKNOWN'.
"""
    try:
        text = _generate_with_retry(prompt)
        if "UNKNOWN" in text:
            return None
        return text.strip()
    except Exception as e:
        print(f"[AI ERROR] Halt Date Extraction failed: {e}")
        return None

