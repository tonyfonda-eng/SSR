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
# Pool stores tuples: (provider_name, client_instance)
clients = []

for k in or_keys:
    # OpenRouter uses the OpenAI SDK structure
    client = openai.Client(
        base_url="https://openrouter.ai/api/v1",
        api_key=k,
    )
    clients.append(("openrouter", client))

for k in gemini_keys:
    client = genai.Client(api_key=k)
    clients.append(("gemini", client))

print(f"[AI INFO] Initialized {len(or_keys)} OpenRouter clients and {len(gemini_keys)} Gemini clients.")

def _generate_with_retry(prompt, max_retries=6):
    if not clients:
        raise ValueError("GEMINI_API_KEY not set")
    
    import time
    import re
    available_clients = list(clients)
    random.shuffle(available_clients)
    
    last_error = None
    for attempt in range(max_retries):
        for client in list(available_clients):
            try:
                response = client.models.generate_content(
                    model='gemini-flash-latest',
                    contents=prompt,
                )
                return response.text.strip()
            except Exception as e:
                last_error = e
                error_str = str(e)
                if "429" in error_str or "RESOURCE_EXHAUSTED" in error_str:
                    if "GenerateRequestsPerDay" in error_str:
                        print("[AI RETRY] Key hit absolute daily quota. Removing from pool.")
                        available_clients.remove(client)
                        if not available_clients:
                            raise ValueError("CRITICAL: All API keys have exhausted their daily Free Tier quota.")
                        continue # Swap to next key instantly
                        
                    # Standard RPM rate limit, swap to next key instantly
                    continue
                else:
                    # Other API error, swap to next key instantly
                    continue
                    
        # If we reach here, we've looped through ALL available keys and they ALL failed.
        # Now we must sleep before trying the next cycle.
        wait_time = 20
        if last_error:
            match = re.search(r'retry in (\d+(?:\.\d+)?)s', str(last_error))
            if match:
                wait_time = max(20, int(float(match.group(1))) + 2)
                
        print(f"[AI RETRY] All available keys rate-limited. Sleeping {wait_time}s before next cycle (Attempt {attempt+1}/{max_retries})...")
        time.sleep(wait_time)
        
    raise last_error

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
Structured fields only: Event Family, Subtype, Status, Target, Acquirer, Jurisdiction, Exchange.

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
        return f"[AI ERROR] {e}"

def check_material_update(article_text, event_family, ticker, previous_summary=None):
    """
    Checks if a duplicate article contains material new information compared to what we already know.
    """
    if not clients:
        return False
        
    context_str = ""
    if previous_summary:
        context_str = f"\n\n--- WHAT WE ALREADY KNOW (Previous AI Summary) ---\n{previous_summary}\n----------------------------------------------------\n\n"
        
    prompt = f"""
You are an expert financial analyst. 
We are already tracking a '{event_family}' involving the target company '{ticker}'.{context_str}
Read the following new article. Does it contain NEW, material information that warrants updating our case file?
Examples of material updates:
- A competing bidder has emerged.
- The deal price/premium has been bumped.
- A major regulatory approval or block was announced.
- Shareholder vote results.
- Deal termination or broken deal.

Examples of non-material updates (syndicated noise):
- Law firms announcing "investigations" into the merger.
- Another news outlet just repeating the exact same original announcement facts that we already know.
- Generic PR boilerplate about the merger that contains no new milestones.

CRITICAL: If the new article contains the exact same information as "WHAT WE ALREADY KNOW" (e.g. it's just the same press release published on a different newswire), you MUST answer NO.

Answer strictly with YES or NO on the first line. 
On the second line, provide a 1-sentence explanation.

Article text:
{article_text[:6000]}
"""
    try:
        text = _generate_with_retry(prompt).upper()
        return text.startswith("YES")
    except Exception as e:
        print(f"[AI ERROR] All keys exhausted or failed: {e}")
        return False

def translate_to_english(text):
    """
    Translates foreign language financial text to English using Gemini Flash.
    Used for European/International sources before they hit the Rules Engine.
    """
    if not clients:
        return text
        
    prompt = f"""
Translate the following financial text into English. 
Return ONLY the English translation. Maintain all financial terminology, company names, and ticker symbols exactly as they appear conceptually. Do not summarize or add commentary.

Text:
{text[:6000]}
"""
    try:
        return _generate_with_retry(prompt)
    except Exception as e:
        print(f"[AI ERROR] Translation failed: {e}")
        return text

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
If the company is private, or if you cannot determine the ticker, return exactly 'PRIVATE'.
Return NOTHING ELSE besides the ticker or 'PRIVATE'.
"""
    try:
        text = _generate_with_retry(prompt)
        return text.upper()
    except Exception as e:
        print(f"[AI ERROR] Ticker Extraction failed: {e}")
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

