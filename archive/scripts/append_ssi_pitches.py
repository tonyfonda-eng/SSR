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
        worksheet = sheet.add_worksheet(title="AI Gold Standards", rows=100, cols=10)
        worksheet.append_row(["Event Family", "Gold Standard Example"])

    # Pitch 1: Enhabit (EHAB)
    ehab_text = """#### **[USER INPUT TO AGENT]:**

> Analyze this deal and evaluate the setup:
> Target: Enhabit (EHAB)
> Acquirer: Kinderhook Industries
> Spread: 2.2%
> This is a small bidding war setup... Kinderhook signed a definitive agreement... Party G was planning to submit a new Acquisition Proposal... flip-flopping from Party G... close to zero now... EHAB will most likely just get taken out by Kinderhook.

---

#### **[EXPECTED AGENT OUTPUT]:**

### 1. Catalyst Evaluation: Enhabit (EHAB)

* **System Classification:** **APPROVE** (Fits Competing Bid / Bidding War Strategy)
* **Target:** Enhabit (EHAB)
* **Acquirer:** Kinderhook Industries
* **Current Spread:** 2.2%

#### Strategy Fit & Analysis

1. **Definitive Agreement:** Kinderhook Industries has signed a definitive agreement to acquire the company.
2. **Competing Bidder Exit:** A potential competing bidder ("Party G") had informed Goldman Sachs they would submit a new Acquisition Proposal, but subsequently dropped out.
3. **Closing Probability:** With Party G dropping out of the bidding war, the odds of another interloper emerging are extremely low. The transaction is highly likely to close with Kinderhook.

#### Key Risk Flags

* **Spread Compression:** The spread has already compressed to 2.2% (down from 5.6%), reflecting the market's high confidence that the Kinderhook deal will close."""

    # Pitch 2: Webjet Group (WJL.AX)
    wjl_text = """#### **[USER INPUT TO AGENT]:**

> Analyze this deal and evaluate the setup:
> Guest Pitch: Webjet Group (WJL.AX)
> Helloworld (HLO) bought more shares moving from 18.294% to 19.95%. At 19.95%, it is effectively capped under the Australian 20% rule from further normal on-market buying, so the next logical route to control is a formal takeover bid directly with shareholders. HLO’s move keeps a lower hostile/semi-hostile bid, maybe A$0.60–A$0.65 as a possibility.

---

#### **[EXPECTED AGENT OUTPUT]:**

### 1. Catalyst Evaluation: Webjet Group (ASX: WJL)

* **System Classification:** **APPROVE** (Fits Activist Campaign Strategy)
* **Target:** Webjet Group (ASX: WJL)
* **Aggressor / Potential Acquirer:** Helloworld (HLO)

#### Strategy Fit & Analysis

1. **Creeping Takeover:** Helloworld (HLO) has aggressively accumulated shares, moving its stake from 18.294% to 19.95%.
2. **Statutory Threshold Reached:** Under Australian takeover laws, HLO is capped at 20% for creeping on-market purchases. 
3. **Next Logical Catalyst:** Because HLO cannot purchase more shares on the open market, the only path to achieving control is to launch a formal takeover bid directly to shareholders.
4. **Valuation Floor:** The aggressive block buying establishes a strong valuation floor and signals intent for a hostile or semi-hostile bid, estimated in the A$0.60–A$0.65 range.

#### Key Risk Flags

* **Timing & Capital Tie-up:** The timing of a formal bid is uncertain, and capital may be tied up while waiting for HLO's next move."""

    new_rows = [
        ["Competing Bid / Bidding War", ehab_text],
        ["Activist Campaign", wjl_text]
    ]

    for row in new_rows:
        event_family, gold_standard_text = row
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
