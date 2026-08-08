import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.sheets import get_spreadsheet
from src.config.settings import SHEET_URL

def setup_ai_prompts_tab():
    print("Setting up 'AI Prompts' tab in Google Sheets...")
    spreadsheet = get_spreadsheet(SHEET_URL)
    
    tab_title = "AI Prompts"
    try:
        worksheet = spreadsheet.worksheet(tab_title)
        print(f"Tab '{tab_title}' already exists. Overwriting with default template...")
        worksheet.clear()
    except Exception:
        print(f"Tab '{tab_title}' not found. Creating it...")
        worksheet = spreadsheet.add_worksheet(title=tab_title, rows=20, cols=5)
    
    # Define headers
    headers = ["Prompt ID", "Role", "Description", "System Prompt Template", "Output JSON Schema"]
    worksheet.update(values=[headers], range_name='A1:E1')
    
    # Define default prompt for Event Classification
    classification_prompt = (
        "Analyze this corporate text and the associated rule triggers.\n"
        "Categorize the event into EXACTLY ONE of these families:\n"
        "- Merger\n"
        "- Acquisition\n"
        "- Spin-off\n"
        "- Tender\n"
        "- Joint Venture\n"
        "- Restructuring\n"
        "- Distressed Sale\n"
        "- Asset Purchase\n"
        "- Take-private\n"
        "- Minority Investment\n"
        "- Strategic Partnership\n"
        "- Resumption of Trading\n"
        "- Unknown\n"
        "- False Positive\n\n"
        "{context_str}\n"
        "Rule Triggers: {match_context}\n\n"
        "Text: {body_text}"
    )
    
    classification_schema = (
        '{\n'
        '  "classification": "One of the exact family names listed above",\n'
        '  "rationale": "A brief 1-2 sentence explanation of why this text matches the chosen classification or why it was rejected as a False Positive."\n'
        '}'
    )
    
    default_rules = [
        ["CLASSIFY_EVENT_V1", "System", "Main event classification prompt used in Stage 4 of the pipeline.", classification_prompt, classification_schema]
    ]
    
    worksheet.update(values=default_rules, range_name='A2:E2')
    
    # Format header
    worksheet.format("A1:E1", {
        "textFormat": {"bold": True}
    })
    
    print(f"Successfully configured '{tab_title}'.")

if __name__ == "__main__":
    setup_ai_prompts_tab()
