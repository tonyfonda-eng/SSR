import src.sheets as sheets

SHEET_URL = "https://docs.google.com/spreadsheets/d/1YDOyc8WReBei-7LKPLiXZtmOGCmoY7zuyTvyfMHeL4E/edit#gid=0"

try:
    gc = sheets.get_client()
    sh = gc.open_by_url(SHEET_URL)
    
    # Try to add the worksheet
    try:
        ws = sh.add_worksheet(title="Normalization Review", rows=1000, cols=6)
        ws.append_row(["Date", "Source", "Language", "Document Type", "Title", "URL"])
        
        # Make the header bold
        ws.format("A1:F1", {"textFormat": {"bold": True}})
        print("Created 'Normalization Review' tab successfully!")
    except Exception as e:
        print(f"Worksheet might already exist: {e}")
        
except Exception as e:
    print(f"Error: {e}")
