import src.sheets as sheets

SHEET_URL = "https://docs.google.com/spreadsheets/d/1YDOyc8WReBei-7LKPLiXZtmOGCmoY7zuyTvyfMHeL4E/edit#gid=0"

sources_to_add = [
    {
        "Enabled": "TRUE", "Priority": "High", "Source": "EQS News (Germany)", 
        "Country": "Germany", "Language": "German/English", "Regulator": "BaFin", "Distributor": "EQS",
        "Type": "RSS", "HTML URL": "https://www.eqs-news.com/", "Status": "Active", "Ingestion Method": "Google News Bridge"
    },
    {
        "Enabled": "TRUE", "Priority": "High", "Source": "eMarket SDIR (Italy)", 
        "Country": "Italy", "Language": "Italian/English", "Regulator": "CONSOB", "Distributor": "Teleborsa",
        "Type": "RSS", "HTML URL": "https://www.emarketstorage.it/", "Status": "Active", "Ingestion Method": "Google News Bridge"
    },
    {
        "Enabled": "TRUE", "Priority": "High", "Source": "AMF (France)", 
        "Country": "France", "Language": "French", "Regulator": "AMF", "Distributor": "AMF",
        "Type": "RSS", "HTML URL": "https://amf-france.org/", "Status": "Active", "Ingestion Method": "Google News Bridge"
    },
    {
        "Enabled": "TRUE", "Priority": "High", "Source": "CNMV (Spain)", 
        "Country": "Spain", "Language": "Spanish/English", "Regulator": "CNMV", "Distributor": "CNMV",
        "Type": "RSS", "HTML URL": "https://www.cnmv.es/", "Status": "Active", "Ingestion Method": "Google News Bridge"
    },
    {
        "Enabled": "TRUE", "Priority": "High", "Source": "Finansinspektionen (Sweden)", 
        "Country": "Sweden", "Language": "Swedish/English", "Regulator": "FI", "Distributor": "FI",
        "Type": "RSS", "HTML URL": "https://www.fi.se/", "Status": "Active", "Ingestion Method": "Google News Bridge"
    },
    {
        "Enabled": "TRUE", "Priority": "High", "Source": "NewsWeb (Norway)", 
        "Country": "Norway", "Language": "Norwegian/English", "Regulator": "Finanstilsynet", "Distributor": "Oslo Børs",
        "Type": "RSS", "HTML URL": "https://newsweb.oslobors.no/", "Status": "Active", "Ingestion Method": "Google News Bridge"
    },
    {
        "Enabled": "TRUE", "Priority": "High", "Source": "AFM (Netherlands)", 
        "Country": "Netherlands", "Language": "Dutch/English", "Regulator": "AFM", "Distributor": "AFM",
        "Type": "RSS", "HTML URL": "https://www.afm.nl/", "Status": "Active", "Ingestion Method": "Google News Bridge"
    },
    {
        "Enabled": "TRUE", "Priority": "High", "Source": "SIX Exchange (Switzerland)", 
        "Country": "Switzerland", "Language": "German/French/English", "Regulator": "FINMA", "Distributor": "SIX",
        "Type": "RSS", "HTML URL": "https://www.six-group.com/", "Status": "Active", "Ingestion Method": "Google News Bridge"
    }
]

try:
    gc = sheets.get_client()
    sh = gc.open_by_url(SHEET_URL)
    ws = sh.worksheet("Sources")
    
    # 1. Delete rows added in previous iteration to avoid duplicates
    records = ws.get_all_records()
    headers = ws.row_values(1)
    
    # Reverse iteration to delete safely
    for i in range(len(records), 0, -1):
        source_name = records[i-1].get("Source", "")
        # Delete if it matches old or new names
        if any(name in source_name for name in ["EQS News", "Actusnews", "CNMV", "eMarket SDIR", "Euronext", "AMF", "Finansinspektionen", "NewsWeb", "AFM", "SIX Exchange"]):
            ws.delete_rows(i + 1)
            print(f"Deleted old source: {source_name}")

    # 2. Append 8 new structured sources
    rows_to_append = []
    for s in sources_to_add:
        row = []
        for h in headers:
            row.append(s.get(h, ""))
        rows_to_append.append(row)
        
    ws.append_rows(rows_to_append)
    print("Appended 8 fully structured OAM sources to the Google Sheet!")
except Exception as e:
    print("Error:", e)
