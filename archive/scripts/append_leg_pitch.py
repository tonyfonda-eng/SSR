import gspread
from google.oauth2.service_account import Credentials
import os
import json

def append_gold_standards():
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
        print("Error: AI Gold Standards worksheet not found.")
        return

    # Pitch 3: Leggett & Platt (LEG)
    leg_text = """#### **[USER INPUT TO AGENT]:**

> Analyze this deal and evaluate the setup:
> Target: Leggett & Platt (LEG)
> Potential Acquirers: Tempur Sealy (TPX) or Private Equity (e.g., Apollo)
> According to recent rumors/reporting, Leggett & Platt (LEG), a diversified manufacturer of engineered components and products, has initiated a formal strategic review process. Several private equity firms have allegedly expressed interest. Given the company's recent struggles... a sale of the whole company seems like a highly probable outcome...

---

#### **[EXPECTED AGENT OUTPUT]:**

### 1. Catalyst Evaluation: Leggett & Platt (LEG)

* **System Classification:** **APPROVE** (Fits Strategic Review / Sale Process Strategy)
* **Target:** Leggett & Platt (LEG)
* **Potential Acquirers:** Tempur Sealy (TPX), Private Equity (Apollo, etc.)

#### Strategy Fit & Analysis

1. **Strategic Review Initiated:** The company has officially or via credible reporting initiated a formal strategic review process, indicating the board is open to exploring a sale or significant corporate action.
2. **Private Equity Interest:** Several private equity firms have already expressed preliminary interest, increasing the likelihood of a competitive bidding process.
3. **Turnaround / Take-Private Candidate:** Given recent operational struggles, a sale of the entire company to a private buyer who can execute a turnaround out of the public eye is a highly probable outcome.

#### Key Risk Flags

* **Financing Risk:** With current interest rates, the buyer's ability to secure debt financing (if PE) will dictate the final premium offered.
* **Process Collapse:** Strategic reviews do not always result in a sale. If bids do not meet the board's valuation expectations, the process could collapse, resulting in a severe drop in share price."""

    event_family = "Strategic Review / Sale Process"
    gold_standard_text = leg_text
    
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
    append_gold_standards()
