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

    # Pitch 4: Perfect Corp (PERF)
    perf_text = """#### **[USER INPUT TO AGENT]:**

> Analyze this deal and evaluate the setup:
> Target: Perfect Corp (PERF)
> The founder group has signed a definitive agreement to take the company private. The final deal is $2/share in cash. The deal requires approval by 2/3 of the votes cast. The founder group owns 81% of the total voting power, making approval a formality. Q4 close planned. Can anyone confirm whether there will be an ADR redemption fee (often $0.05 for a Cayman Island based entity). PERF has NYSE-listed ordinary shares, so I think ADR fees are not applicable here.

---

#### **[EXPECTED AGENT OUTPUT]:**

### 1. Catalyst Evaluation: Perfect Corp (PERF)

* **System Classification:** **APPROVE** (Fits Chinese Going-Private / ADR Strategy)
* **Target:** Perfect Corp (PERF)
* **Acquirer:** Founder Group Management Buyout (MBO)
* **Stated Deal Price (Cash Ceiling):** $2.00 cash per share

#### Strategy Fit & Analysis

1. **Definitive Agreement:** A binding agreement has been reached to take the company private for $2.00 per share in cash.
2. **Voting Power Guarantee:** The transaction requires a 2/3 majority of votes cast to be approved. The founder group (the acquirer) already owns 81% of the total voting power. Therefore, shareholder approval is a mathematical certainty and merely a formality.
3. **ADR Fee Mitigation:** The company has ordinary shares listed on the NYSE, meaning the typical $0.05 ADR cancellation/redemption fee charged by depositary banks does not apply to this spread.

#### Key Risk Flags

* **Regulatory Approvals:** While shareholder approval is guaranteed, any standard regulatory approvals required for closing in Q4 must still be monitored.
* **Financing Risk:** Must verify that the founder group has committed financing in place."""

    event_family = "Chinese Going-Private / ADR"
    gold_standard_text = perf_text
    
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
