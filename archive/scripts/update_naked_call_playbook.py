import gspread
from google.oauth2.service_account import Credentials
import os
import json

def update_naked_call_playbook():
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
    
    playbooks_sheet = sheet.worksheet("Playbooks")
    records = playbooks_sheet.get_all_records()
    
    new_instructions = """Playbook: Cash Acquisition Option Premium Strategy
Objective
Identify definitive 100% cash acquisitions where the takeover price creates a credible valuation ceiling, and determine whether selling out-of-the-money call options above that ceiling is structurally attractive.
The AI must produce factual analysis, not trading advice.

1. Transaction Qualification
The transaction qualifies only if all of the following are true:
- Definitive merger agreement signed.
- 100% cash consideration.
- Publicly listed target.
- Exchange-listed options available.
- Fixed cash offer.
- Expected closing date disclosed.
Reject immediately: Rumours, Non-binding proposals, Strategic reviews, Stock-for-stock deals, Mixed consideration, Asset purchases, Private-company acquisitions

2. Extract Required Information
- Parties: Target company, Target ticker, Acquirer
- Deal Terms: Cash offer per share, Offer premium, Current share price, Current merger spread (%), Expected closing date
- Option Market: Listed options available (Yes/No), Available expiries, Open interest, Bid/ask spreads, Trading liquidity

3. Ceiling Assessment
Determine whether the takeover price is likely to remain an effective ceiling.
Assess:
- Is consideration fixed?
- Any mechanism allowing the offer price to increase?
- Any contingent value rights (CVRs), earn-outs, or variable consideration?
If the ceiling is not fixed, reject the opportunity.

4. Ceiling Risk Assessment
Extract and summarise:
- Go-Shop / No-Shop: Determine whether the merger agreement contains a Go-shop period, No-shop clause, or Fiduciary out. Summarise what these provisions mean for the probability of a competing bid.
- Termination / Break Fees: Extract Buyer termination fee, Seller termination fee, Percentage of equity value (if calculable). Comment whether the fees appear Low, Typical, or High. Explain whether they make competing bids more or less likely.
- Competing Bid Risk: Determine any known rival bidders, Active auction process, Previous competing offers, Market speculation of additional bidders. Assign: Low, Medium, High.

5. Option Strategy Assessment
Calculate: Deal price, Current share price, Distance to ceiling, Spread (%), Days until expected close.
Identify candidate strikes approximately: 5%, 10%, 15% above the cash consideration.
For each strike report: Premium, Bid, Ask, Open interest, Volume.

6. Strategy Assessment
Provide scores (0–100): Ceiling Strength, Deal Certainty, Competing Bid Risk (inverse score), Option Liquidity, Premium Attractiveness, Overall Strategy Score.

7. Investment Memo
Produce:
- Executive Summary
- Why the Ceiling Exists
- What Could Break the Ceiling: Focus specifically on Higher offer, Go-shop process, Fiduciary out, Competing bidder
- Option Market Summary
- Key Dates: Announcement, Go-shop expiry (if applicable), Expected closing
- Overall Assessment (Choose one: Attractive Premium Opportunity, Worth Monitoring, Not Suitable)
- Unknowns: List any important information that could not be confirmed."""

    updated = False
    for i, r in enumerate(records):
        if r.get("Playbook", "") == "M&A Naked Call Strategy":
            row = i + 2 # +2 for 1-index and header
            playbooks_sheet.update(f"B{row}", [[new_instructions]])
            print(f"Successfully updated Playbook instructions on row {row}")
            updated = True
            break
            
    if not updated:
        playbooks_sheet.append_row(["M&A Naked Call Strategy", new_instructions])
        print("Appended new Playbook instructions.")

if __name__ == "__main__":
    update_naked_call_playbook()
