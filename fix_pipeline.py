from src.config.settings import SHEET_URL
from src.sheets import get_client
import gspread

def fix_pipeline():
    client = get_client()
    sheet = client.open_by_url(SHEET_URL)
    
    # Try different possible names for the Pipeline tab
    worksheet = None
    for name in ["Pipeline", "Process", "Execution Pipeline"]:
        try:
            worksheet = sheet.worksheet(name)
            break
        except gspread.exceptions.WorksheetNotFound:
            pass
            
    if not worksheet:
        print("Could not find Pipeline worksheet.")
        return
        
    all_values = worksheet.get_all_values()
    headers = all_values[0]
    
    stage_id_idx = headers.index("Stage_ID")
    order_idx = headers.index("Order")
    
    for i in range(1, len(all_values)):
        row = all_values[i]
        if len(row) <= max(stage_id_idx, order_idx):
            continue
            
        stage_id = row[stage_id_idx].strip()
        
        # New DAG Order logic
        if stage_id == "python_ticker_lookup":
            row[order_idx] = "10"
        elif stage_id == "ai_ticker_resolution":
            row[order_idx] = "11"
        elif stage_id == "entity_confidence":
            row[order_idx] = "12"
        elif stage_id == "tradeability_check":
            row[order_idx] = "13"
        elif stage_id == "liquidity_check":
            row[order_idx] = "14"
        elif stage_id == "financial_market_cap":
            row[order_idx] = "15"
        elif stage_id == "financial_t12_floor":
            row[order_idx] = "16"
        elif stage_id == "options_chain_check":
            row[order_idx] = "17"
        elif stage_id == "playbook_gate":
            row[order_idx] = "18"
            
        all_values[i] = row
        
    worksheet.update("A1", all_values)
    print("Successfully updated Pipeline execution order in Google Sheet.")

if __name__ == "__main__":
    fix_pipeline()
