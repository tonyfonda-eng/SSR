import src.sheets as sheets
import pprint

SHEET_URL = "https://docs.google.com/spreadsheets/d/1YDOyc8WReBei-7LKPLiXZtmOGCmoY7zuyTvyfMHeL4E/edit#gid=0"

new_sources = [
    {
        "Enabled": "TRUE",
        "Priority": "High",
        "Source": "SEC EDGAR - Tender Offers (SC TO)",
        "Type": "HTML",
        "HTML URL": "https://www.sec.gov/cgi-bin/browse-edgar?action=getcurrent&type=SC+TO",
        "Status": "Active",
        "Ingestion Method": "HTML",
        "Parsed (Last Run)": 0,
        "Cumulative Parsed (Today)": 0
    },
    {
        "Enabled": "TRUE",
        "Priority": "High",
        "Source": "SEC EDGAR - Board Rec (14D-9)",
        "Type": "HTML",
        "HTML URL": "https://www.sec.gov/cgi-bin/browse-edgar?action=getcurrent&type=SC+14D9",
        "Status": "Active",
        "Ingestion Method": "HTML",
        "Parsed (Last Run)": 0,
        "Cumulative Parsed (Today)": 0
    },
    {
        "Enabled": "TRUE",
        "Priority": "High",
        "Source": "SEC EDGAR - Merger Proxy (PREM14A)",
        "Type": "HTML",
        "HTML URL": "https://www.sec.gov/cgi-bin/browse-edgar?action=getcurrent&type=PREM14A",
        "Status": "Active",
        "Ingestion Method": "HTML",
        "Parsed (Last Run)": 0,
        "Cumulative Parsed (Today)": 0
    },
    {
        "Enabled": "TRUE",
        "Priority": "High",
        "Source": "SEC EDGAR - Definitive Proxy (DEFM14A)",
        "Type": "HTML",
        "HTML URL": "https://www.sec.gov/cgi-bin/browse-edgar?action=getcurrent&type=DEFM14A",
        "Status": "Active",
        "Ingestion Method": "HTML",
        "Parsed (Last Run)": 0,
        "Cumulative Parsed (Today)": 0
    },
    {
        "Enabled": "TRUE",
        "Priority": "High",
        "Source": "SEC EDGAR - S-4 (Stock Mergers)",
        "Type": "HTML",
        "HTML URL": "https://www.sec.gov/cgi-bin/browse-edgar?action=getcurrent&type=S-4",
        "Status": "Active",
        "Ingestion Method": "HTML",
        "Parsed (Last Run)": 0,
        "Cumulative Parsed (Today)": 0
    }
]

try:
    gc = sheets.get_client()
    sh = gc.open_by_url(SHEET_URL)
    ws = sh.worksheet("Sources")
    
    headers = ws.row_values(1)
    
    # 1. Add the 5 new sources
    rows_to_append = []
    for s in new_sources:
        row = []
        for h in headers:
            row.append(s.get(h, ""))
        rows_to_append.append(row)
        
    ws.append_rows(rows_to_append)
    print("Added 5 new EDGAR sources to the Google Sheet!")
    
    # 2. Disable Dedupe for "Special Situations Digest"
    records = ws.get_all_records()
    col_idx_dedupe = headers.index("Dedupe") + 1
    
    for i, r in enumerate(records):
        if "Special Situations Digest" in str(r.get("Source", "")):
            row_idx = i + 2 # +2 because 1-indexed and header row
            cell = sheets.gspread.utils.rowcol_to_a1(row_idx, col_idx_dedupe)
            ws.update(cell, "FALSE")
            print(f"Disabled deduplication for Special Situations Digest at row {row_idx}")
            break
            
except Exception as e:
    print("Error:", e)
