import gspread
from google.oauth2.service_account import Credentials
import os
import json

def append_gold_standard():
    # Setup credentials
    creds_json = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON")
    if not creds_json:
        print("Error: GOOGLE_SERVICE_ACCOUNT_JSON not set")
        return
        
    creds_dict = json.loads(creds_json)
    SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
    credentials = Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
    client = gspread.authorize(credentials)
    
    sheet_url = "https://docs.google.com/spreadsheets/d/1YDOyc8WReBei-7LKPLiXZtmOGCmoY7zuyTvyfMHeL4E/edit#gid=0"
    sheet = client.open_by_url(sheet_url)
    
    try:
        worksheet = sheet.worksheet("AI Gold Standards")
    except gspread.exceptions.WorksheetNotFound:
        worksheet = sheet.add_worksheet(title="AI Gold Standards", rows=100, cols=10)
        worksheet.append_row(["Event Family", "Gold Standard Example"])
        
    event_family = "Strategic Review / Sale Process"
    
    gold_standard_text = """1. Executive Summary
Noodles & Company (NDLS) has been conducting a strategic review for nine months and appears poised for a potential sale. Operating performance has inflected positively following a turnaround led by activist Mill Road Capital (15% stake). Management recently received change-of-control retention bonuses expiring December 2026. The stock trades at <5x 2026 EBITDA, presenting a 40-65% upside if sold at a conservative 5.5-6x multiple. Initial review recommended.

2. Event Classification
* **Event Family:** Strategic Review / Sale Process
* **Subtype:** Potential Sale / Turnaround
* **Status:** Ongoing Strategic Review
* **Target:** Noodles & Company (NDLS)
* **Acquirer:** N/A (Searching for buyer)
* **Jurisdiction:** United States
* **Exchange:** NASDAQ

4. Investment Facts & Returns
* **Current Price:** $10.97 (implied from write-up)
* **Implied Target Sale Price:** $15.00 - $18.00 per share (at 5.5-6x EBITDA)
* **Gross Spread (%):** 36.7% to 64.1% upside
* **Estimated Annualized IRR:** N/A (No definitive close date)
* **Activist Ownership:** >50% aggregate across 5 funds (Mill Road Capital at 15%)
* **Valuation Multiple:** 4.8x 2026E Adjusted EBITDA ($30-$35m)
* **Retention Bonus Deadline:** December 2026
* **Comparable Transactions:** Del Taco (6.5x), Fiesta (7.3x)

5. Risk Assessment
* **Primary Risks:** Turnaround proves fragile and operational momentum (Q1/Q2 SSS growth) reverts; failure to find a buyer could collapse the stock to ~$6.
* **Unknowns:** The actual progress of the strategic review; identity of potential buyers; willingness of board to sell at current levels.

6. Market Context
* **Insider/Activist Ownership:** Five activists own over 50% combined, creating strong pressure to realize value.
* **Turnaround Progress:** Management replaced, menu overhauled, store closures mitigating cash burn, and same-store sales rebounding strongly (7-9% recently).
* **Strategic Motivation:** Change-of-control retention bonuses actively incentivize management to sell the company by December 2026.

7. Trading Relevance
* **Liquidity & Market Cap:** Micro-cap (~$67M equity, $172M EV). Highly illiquid, making it difficult for large institutional arbitrage funds.
* **Target Audience:** Special situations funds and micro-cap value investors.

8. Missing Information
* Whether formal bids have been received or an auction is taking place.
* Refinancing terms if a sale does not occur (debt matures July 2027).

9. Suggested Next Reading
* The Q2 2026 Earnings Call Transcript (for updates on the strategic review).
* The 8-K filings detailing the executive change-of-control retention agreements.

10. AI Opinion
This is a classic activist-driven strategic review with aligned management incentives (retention bonuses). The massive discount to historical restaurant transaction multiples offers a margin of safety, assuming the recent earnings inflection is genuine. The main red flag is the micro-cap nature and high leverage, making it a binary play.

11. Checklist Table
| Question | Answer |
| :--- | :--- |
| Public target? | Yes |
| Cash event? | Potential (Strategic Review) |
| Actionable? | Yes |
| Premium disclosed? | No (Theoretical 40-65% upside) |
| Financing disclosed? | N/A |
| Board support? | N/A (Board exploring sale) |
| Immediate review required? | Yes |

12. Analyst To-Do List
* Review the Q1 and Q2 2026 earnings reports to verify the sustainability of the same-store sales turnaround.
* Read the executive retention agreements to confirm the exact mechanics and December 2026 deadline.
* Map out the debt maturity profile (July 2027) to assess the downside risk if no deal occurs."""
    
    # Check if this family already has a gold standard, if so, update it, else append
    records = worksheet.get_all_records()
    row_to_update = -1
    for i, r in enumerate(records):
        if r.get('Event Family') == event_family:
            row_to_update = i + 2 # +2 because 1-indexed and header row
            break
            
    if row_to_update != -1:
        worksheet.update(f"B{row_to_update}", [[gold_standard_text]])
        print(f"Updated existing Gold Standard for {event_family}")
    else:
        worksheet.append_row([event_family, gold_standard_text])
        print(f"Appended new Gold Standard for {event_family}")

if __name__ == "__main__":
    append_gold_standard()
