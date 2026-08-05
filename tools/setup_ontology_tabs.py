"""
One-time setup script to create/update Google Sheets tabs for Ontology V3.

Creates:
  1. "Semantic Concepts" tab with 12 core corporate action concepts
  2. "Event Status" tab with 6 deal stage statuses
  3. Renames "Normalization Review" → "Ontology Review" (or creates new)
  4. Verifies "Document Types" tab exists

Usage:
    python setup_ontology_tabs.py
"""
import gspread
from src.sheets import get_client

SHEET_URL = "https://docs.google.com/spreadsheets/d/1YDOyc8WReBei-7LKPLiXZtmOGCmoY7zuyTvyfMHeL4E/edit#gid=0"

# --- 12 Core Semantic Concepts ---
CONCEPTS = [
    ["Concept_ID", "Description", "Score", "Countries", "Languages", "Examples"],
    ["ACQUISITION", "Company buying another company", "40", "ALL",
     "English: acquisition, purchase, takeover, acquire, acquired; German: übernahme; French: acquisition; Italian: acquisizione; Spanish: adquisición; Dutch: overname; Swedish: förvärv; Norwegian: oppkjøp",
     "Company X to acquire Company Y"],
    ["MERGER", "Two public companies combining", "40", "ALL",
     "English: merger, merge, merging; German: fusion; French: fusion; Italian: fusione; Spanish: fusión; Dutch: fusie; Swedish: fusion",
     "Company X and Y announce merger"],
    ["TENDER_OFFER", "Public offer to shareholders", "45", "ALL",
     "English: tender offer, cash offer, recommended offer, recommended cash offer; German: barangebot, übernahmeangebot; French: offre publique d'achat, offre publique; Italian: offerta pubblica; Spanish: oferta pública de adquisición, opa; Dutch: openbaar bod; Swedish: uppköpserbjudande; Norwegian: tilbud",
     "Files tender offer for $X/share"],
    ["TAKE_PRIVATE", "Public company becoming private", "40", "ALL",
     "English: take private, taken private, going-private, privatization, privatisation",
     "PE firm to take Company X private"],
    ["GOING_PRIVATE", "Same concept from issuer perspective", "40", "ALL",
     "English: going private, go-private, rule 13e-3",
     "Company X announces going-private transaction"],
    ["DELISTING", "Removal from exchange", "35", "ALL",
     "English: delisting, delist, delisted, removal from listing; German: delisting",
     "Company X to delist from NYSE"],
    ["SPIN_OFF", "Separation of business", "30", "ALL",
     "English: spin-off, spinoff, spin off, separation, demerger; German: abspaltung",
     "Company X to spin off division"],
    ["LIQUIDATION", "Wind-down / distribution", "35", "ALL",
     "English: liquidation, wind-down, winding down, dissolution, plan of dissolution; German: insolvenz",
     "Fund announces plan of dissolution"],
    ["SPECIAL_DIVIDEND", "One-off cash payment", "35", "ALL",
     "English: special dividend, extraordinary dividend, one-time dividend; German: sonderdividende",
     "Company declares $X special dividend"],
    ["RETURN_OF_CAPITAL", "Capital reduction/distribution", "30", "ALL",
     "English: return of capital, capital reduction, capital distribution, capital return",
     "Company announces capital return program"],
    ["ACTIVIST_ACTION", "Activist campaign", "20", "ALL",
     "English: activist, proxy fight, board seats, dissident slate, consent solicitation",
     "Activist launches proxy fight"],
    ["STRATEGIC_REVIEW", "Potential future transaction", "15", "ALL",
     "English: strategic review, strategic alternatives, exploring options, exploring strategic",
     "Company X exploring strategic alternatives"],
]

# --- 6 Event Statuses ---
STATUSES = [
    ["Status_ID", "Score", "Languages"],
    ["RUMOUR", "5",
     "English: rumour, rumored, rumoured; German: gerücht; French: rumeur; Spanish: rumor; Dutch: gerucht; Swedish: rykte; Norwegian: rykte"],
    ["POSSIBLE", "10",
     "English: considering, exploring, possible, preliminary discussions, early stage; German: möglich; French: possible; Spanish: posible; Dutch: mogelijk; Swedish: möjlig"],
    ["NON_BINDING", "15",
     "English: non-binding, indicative, preliminary offer, letter of intent; German: unverbindlich; French: non contraignant; Spanish: no vinculante; Italian: non vincolante"],
    ["DEFINITIVE_AGREEMENT", "50",
     "English: definitive agreement, definitive merger agreement, binding agreement, entered into agreement, signed agreement; German: vertrag unterzeichnet; French: accord définitif; Spanish: acuerdo definitivo; Italian: accordo definitivo; Dutch: definitieve overeenkomst; Swedish: bindande avtal"],
    ["COMPLETED", "-10",
     "English: completed, closed, consummated, completion; German: abgeschlossen; French: terminé; Italian: completato; Spanish: completado"],
    ["TERMINATED", "-20",
     "English: terminated, abandoned, withdrawn, called off; German: beendet; French: annulé; Italian: terminato; Spanish: terminado"],
]

# --- Ontology Review Headers ---
ONTOLOGY_REVIEW_HEADERS = [
    "Date", "Country", "Source", "Language", "Document Type",
    "Raw Terms", "Article Title", "Article URL",
    "Detected Concepts", "Suggested Concept", "Status"
]


def main():
    client = get_client()
    sheet = client.open_by_url(SHEET_URL)
    
    existing_tabs = [ws.title for ws in sheet.worksheets()]
    
    # 1. Semantic Concepts
    if "Semantic Concepts" in existing_tabs:
        print("[SKIP] 'Semantic Concepts' tab already exists.")
    else:
        ws = sheet.add_worksheet(title="Semantic Concepts", rows=20, cols=6)
        ws.append_rows(CONCEPTS, value_input_option="RAW")
        print("[CREATED] 'Semantic Concepts' tab with 12 core concepts.")
    
    # 2. Event Status
    if "Event Status" in existing_tabs:
        print("[SKIP] 'Event Status' tab already exists.")
    else:
        ws = sheet.add_worksheet(title="Event Status", rows=10, cols=3)
        ws.append_rows(STATUSES, value_input_option="RAW")
        print("[CREATED] 'Event Status' tab with 6 statuses.")
    
    # 3. Ontology Review (rename or create)
    if "Ontology Review" in existing_tabs:
        print("[SKIP] 'Ontology Review' tab already exists.")
    elif "Normalization Review" in existing_tabs:
        ws = sheet.worksheet("Normalization Review")
        ws.update_title("Ontology Review")
        # Clear and rewrite headers
        ws.clear()
        ws.append_row(ONTOLOGY_REVIEW_HEADERS, value_input_option="RAW")
        print("[RENAMED] 'Normalization Review' → 'Ontology Review' with new headers.")
    else:
        ws = sheet.add_worksheet(title="Ontology Review", rows=100, cols=11)
        ws.append_row(ONTOLOGY_REVIEW_HEADERS, value_input_option="RAW")
        print("[CREATED] 'Ontology Review' tab.")
    
    # 4. Verify Document Types
    if "Document Types" in existing_tabs:
        print("[OK] 'Document Types' tab exists.")
    else:
        print("[WARNING] 'Document Types' tab not found. Please create it manually.")
    
    print("\n[DONE] Ontology V3 tabs are ready.")


if __name__ == "__main__":
    main()
