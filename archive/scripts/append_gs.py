import gspread
from google.oauth2.service_account import Credentials
import os
import json

def append_gold_standard():
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
        
    event_family = "M&A Naked Call Strategy"
    
    gold_standard_text = """#### **[USER INPUT TO AGENT]:**

> Analyze this deal and calculate option yield requirements:
> MKTX to be acquired by ICE for $167.00 cash per share, 32.8% premium, $5.7 billion. Current price $163.10.

---

#### **[EXPECTED AGENT OUTPUT]:**

### 1. Catalyst Evaluation: MarketAxess Holdings Inc. (NASDAQ: MKTX)

* **System Classification:** **APPROVE** (Fits Naked Call Merger Arbitrage Strategy)
* **Target:** MarketAxess Holdings Inc. (NASDAQ: MKTX)
* **Acquirer:** Intercontinental Exchange, Inc. (NYSE: ICE)
* **Stated Deal Price (Cash Ceiling):** $167.00 cash per share
* **Transaction Type:** 100% All-Cash
* **Enterprise Value:** $5.7 Billion
* **Expected Close:** First Half of 2027

#### Strategy Fit & Analysis

1. **Defensible Ceiling:** ICE is paying $167.00 cash. Because this is a strategic acquisition by a major exchange operator, a higher rival bid is unlikely due to high regulatory barriers, establishing a strong price ceiling at $167.00.
2. **Fixed Arbitrage Spread:** Because consideration is 100% cash, MKTX stock will trade independently of ICE share fluctuations.
3. **Volatility Spikes:** The 32.8% premium creates a short-term spike in Implied Volatility (IV), making OTM call premiums attractive to short.

#### Key Risk Flags

* **Regulatory/Antitrust Scrutiny:** FTC/DOJ review could extend the timeline to H1 2027. (Note: A deal delay or collapse lowers the stock price, which benefits naked short calls).
* **Bidding War:** Low risk, but must monitor for competing bids prior to regulatory filings.

---

### 2. Quantitative Options Yield Analysis

* **Selected Strike ($K$):** $170.00 Call ($3.00 above the $167.00 buyout ceiling)
* **Underlying Stock Price ($P$):** $163.10
* **Out-of-the-Money Amount (OTM):** $170.00 - $163.10 = $6.90
* **Reg T Margin Requirement ($M$):**

M = (0.20 * $163.10) - $6.90 = $32.62 - $6.90 = $25.72 per share ($2,572 per contract)


* **Target Annualized ROI:** 20.0% (0.20)
* **Base Annual Yield Required (0.20 * M):** $5.144 per year

#### Option Chain Yield Requirements ($170.00 Strike)

| Expiration Date | Days to Expiration (DTE) | Calculation | Minimum Premium Required |
| --- | --- | --- | --- |
| **August 21, 2026** | 22 Days | $5.144 * (22 / 365) | **$0.31** ($31 per contract) |
| **September 18, 2026** | 50 Days | $5.144 * (50 / 365) | **$0.70** ($70 per contract) |
| **November 20, 2026** | 113 Days | $5.144 * (113 / 365) | **$1.59** ($159 per contract) |
| **February 19, 2027** | 204 Days | $5.144 * (204 / 365) | **$2.87** ($287 per contract) |

*Rule:* If the current market bid for any expiration is **above** the Minimum Premium Required, execute the trade to lock in an annualized return exceeding 20%."""
    
    records = worksheet.get_all_records()
    row_to_update = -1
    for i, r in enumerate(records):
        if r.get('Event Family') == event_family:
            row_to_update = i + 2
            break
            
    if row_to_update != -1:
        worksheet.update(f"B{row_to_update}", [[gold_standard_text]])
        print(f"Updated existing Gold Standard for {event_family}")
    else:
        worksheet.append_row([event_family, gold_standard_text])
        print(f"Appended new Gold Standard for {event_family}")

if __name__ == "__main__":
    append_gold_standard()
