import src.sheets as sheets

SHEET_URL = "https://docs.google.com/spreadsheets/d/1YDOyc8WReBei-7LKPLiXZtmOGCmoY7zuyTvyfMHeL4E/edit#gid=0"

new_sources = [
    {
        "Enabled": "TRUE",
        "Priority": "Medium",
        "Source": "EQS News (Germany)",
        "Type": "RSS",
        "HTML URL": "https://www.eqs-news.com/",
        "Status": "Active",
        "Ingestion Method": "Google News Bridge",
        "Parsed (Last Run)": 0,
        "Cumulative Parsed (Today)": 0
    },
    {
        "Enabled": "TRUE",
        "Priority": "Medium",
        "Source": "Actusnews (France)",
        "Type": "RSS",
        "HTML URL": "https://www.actusnews.com/en/",
        "Status": "Active",
        "Ingestion Method": "Google News Bridge",
        "Parsed (Last Run)": 0,
        "Cumulative Parsed (Today)": 0
    },
    {
        "Enabled": "TRUE",
        "Priority": "Medium",
        "Source": "CNMV (Spain)",
        "Type": "RSS",
        "HTML URL": "https://www.cnmv.es/",
        "Status": "Active",
        "Ingestion Method": "Google News Bridge",
        "Parsed (Last Run)": 0,
        "Cumulative Parsed (Today)": 0
    },
    {
        "Enabled": "TRUE",
        "Priority": "Medium",
        "Source": "eMarket SDIR (Italy)",
        "Type": "RSS",
        "HTML URL": "https://www.emarketstorage.it/",
        "Status": "Active",
        "Ingestion Method": "Google News Bridge",
        "Parsed (Last Run)": 0,
        "Cumulative Parsed (Today)": 0
    },
    {
        "Enabled": "TRUE",
        "Priority": "Medium",
        "Source": "Euronext (Netherlands)",
        "Type": "RSS",
        "HTML URL": "https://live.euronext.com/",
        "Status": "Active",
        "Ingestion Method": "Google News Bridge",
        "Parsed (Last Run)": 0,
        "Cumulative Parsed (Today)": 0
    }
]

try:
    gc = sheets.get_client()
    sh = gc.open_by_url(SHEET_URL)
    ws = sh.worksheet("Sources")
    
    headers = ws.row_values(1)
    
    rows_to_append = []
    for s in new_sources:
        row = []
        for h in headers:
            row.append(s.get(h, ""))
        rows_to_append.append(row)
        
    ws.append_rows(rows_to_append)
    print("Added 5 European OAM sources to the Google Sheet!")
except Exception as e:
    print("Error:", e)
