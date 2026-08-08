import sys
import os

# Add project root to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.sheets import get_spreadsheet
from src.config.settings import SHEET_URL

def setup_audit_protocol_tab():
    print(f"Connecting to Google Sheets...")
    spreadsheet = get_spreadsheet(SHEET_URL)
    
    tab_title = "Audit Protocol"
    
    try:
        worksheet = spreadsheet.worksheet(tab_title)
        print(f"Tab '{tab_title}' already exists. Overwriting with standard schema...")
        worksheet.clear()
    except Exception:
        print(f"Creating new tab '{tab_title}'...")
        worksheet = spreadsheet.add_worksheet(title=tab_title, rows=100, cols=10)
    
    # Define headers
    headers = ["Step Order", "Audit Check", "Function Mapping", "Enabled", "Parameters"]
    worksheet.update(values=[headers], range_name='A1:E1')
    
    # Define default rules based on the protocol
    default_rules = [
        [1, "HTTP 200 OK Verification", "audit_connectivity", "TRUE", '{"timeout_seconds": 15}'],
        [2, "Pagination Volume Check", "audit_pagination", "TRUE", '{"min_items": 5, "max_pages": 1}'],
        [3, "Schema & Parsing Fidelity", "audit_schema", "TRUE", '{}'],
        [4, "Deduplication Compatibility", "audit_dedupe", "TRUE", '{}']
    ]
    
    worksheet.update(values=default_rules, range_name='A2:E5')
    
    # Format header
    worksheet.format("A1:E1", {
        "backgroundColor": {"red": 0.8, "green": 0.8, "blue": 0.8},
        "textFormat": {"bold": True}
    })
    
    print(f"Successfully configured '{tab_title}' tab!")

if __name__ == "__main__":
    setup_audit_protocol_tab()
