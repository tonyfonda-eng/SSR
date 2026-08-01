import gspread
import os
from src.config.secrets import get_google_service_account
from google.oauth2.service_account import Credentials

SHEET_URL = "https://docs.google.com/spreadsheets/d/1YDOyc8WReBei-7LKPLiXZtmOGCmoY7zuyTvyfMHeL4E/edit#gid=0"
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

def get_client():
    credentials = Credentials.from_service_account_info(
        get_google_service_account(),
        scopes=SCOPES,
    )
    return gspread.authorize(credentials)

def main():
    client = get_client()
    sheet = client.open_by_url(SHEET_URL)
    
    tab_title = "Decision Pipeline"
    try:
        worksheet = sheet.worksheet(tab_title)
        worksheet.clear()
    except gspread.exceptions.WorksheetNotFound:
        worksheet = sheet.add_worksheet(title=tab_title, rows=30, cols=8)
        
    headers = [
        "Step #", 
        "Pipeline Stage", 
        "Actor", 
        "Action Performed", 
        "Pass Condition", 
        "If Pass...", 
        "If Fail / Reject..."
    ]
    
    pipeline_steps = [
        ["1", "Ingestion", "Scraper (Python)", "Fetch recent articles from News Sources (HTML or RSS)", "Source is 'Enabled' in Sources tab", "Proceed to Step 2", "Ignored"],
        ["2", "Deduplication", "SQLite (Database)", "Check if Source + Article ID already exists in local database", "Article is entirely new", "Proceed to Step 3", "Dropped (Already Processed)"],
        ["3", "Translation (Optional)", "AI (Gemini)", "Translate non-English text to English", "Source 'Needs Translation' = TRUE", "Proceed to Step 4", "N/A (Skipped)"],
        ["4", "Global Exclusions", "Python", "Check title and body against 'Global Exclusions' tab", "No excluded keywords found", "Proceed to Step 5", "Dropped (Global Exclusion Match)"],
        ["5", "Rules Engine (Keyword Scoring)", "Python", "Score article body against Keywords and Confidence Modifiers in 'Rules' tab", "Total Score >= 10", "Proceed to Step 6", "Dropped (Failed to reach 10 points)"],
        ["6", "Ticker Extraction", "AI (Gemini)", "Read article to identify the primary target company's stock ticker", "Ticker is public (not 'PRIVATE')", "Proceed to Step 7", "Dropped (Private Target)"],
        ["7", "Event Classification", "AI (Gemini)", "Match article to an Event Family or reject as noise", "Valid Event Family identified", "Proceed to Step 8", "Dropped (False Positive) OR Logged to 'Unknown Events' tab"],
        ["8", "Options Check", "Python (yfinance)", "If event is 'M&A Naked Call', verify exchange-listed options exist", "Options chain exists", "Proceed to Step 9", "Dropped (No tradable options)"],
        ["9", "Material Update Check", "AI (Gemini)", "If event is ALREADY tracked, check if this article contains material new information", "Material new info found (e.g. price bump)", "Proceed to Step 10", "Dropped (Syndicated Noise / Duplicate News)"],
        ["10", "AI Research (Playbook)", "AI (Gemini)", "Execute specific 'Playbook' prompts and 'Gold Standards' to generate an Investment Memo", "Memo successfully generated", "Proceed to Step 11", "N/A"],
        ["11", "Alerting & Logging", "Python", "Email the Portfolio Manager & Append row to 'AI Research Queue' tab", "Delivery successful", "Saved to SQLite Archive", "N/A"],
        ["12", "Go-Shop Reminders", "Python", "Check Memo for Go-Shop expiry dates and save a future reminder", "Date found", "Reminder saved for future email", "N/A"]
    ]
    
    # Write headers
    worksheet.append_row(headers)
    
    # Write rows
    for step in pipeline_steps:
        worksheet.append_row(step)
        
    # Formatting
    worksheet.format("A1:G1", {
        "backgroundColor": {"red": 0.2, "green": 0.2, "blue": 0.2},
        "textFormat": {"foregroundColor": {"red": 1.0, "green": 1.0, "blue": 1.0}, "bold": True}
    })
    
    print("[SUCCESS] Decision Pipeline tab created and populated in Google Workbook.")

if __name__ == "__main__":
    main()
