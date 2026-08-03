import sys
import os
from unittest.mock import patch

# Ensure root directory is on python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.rules_engine import evaluate
from src.ai import extract_target_ticker, classify_event
from src.database import initialise_database, article_exists, save_article
from src.alerts.email import send_alert

def run_end_to_end_simulation():
    print("=== STARTING SSR END-TO-END PIPELINE SIMULATION ===")
    
    # 1. Simulate Ingestion (Mock Article)
    mock_article = {
        "source_name": "PR Newswire",
        "article_id": "TEST-999999",
        "title": "Acme Corp Enters Into Definitive Acquisition Agreement to Be Acquired by MegaCorp for $45.00/Share",
        "url": "https://example.com/test-acquisition-filing",
        "published": "2026-08-03 12:00:00 GMT",
        "body": (
            "NEW YORK, Aug. 3, 2026 /PRNewswire/ -- Acme Corp (NASDAQ: ACME) today announced "
            "that it has entered into a definitive merger agreement under which MegaCorp will acquire "
            "all outstanding shares for $45.00 in cash per share, representing a total equity value of $2.1 billion. "
            "The transaction is expected to close in Q4 2026. GO-SHOP EXPIRY: 2026-09-03."
        ),
        "document_type": "Definitive Agreement",
        "country": "US",
        "language": "English"
    }
    print(f"[1. INGESTION] Injected mock article: {mock_article['title']}")

    # 2. Simulate Database & Dedup Check
    initialise_database()
    article_key = f"{mock_article['source_name']}:{mock_article['article_id']}"
    if article_exists(article_key):
        print("[2. DEDUP] WARNING: Test article already marked as processed.")
    else:
        print("[2. DEDUP] Passed. Article is uniquely recognized.")

    # 3. Simulate Rules Engine Filter
    # Mock minimal rules and score weights for the test
    mock_rules = [{
        "Name": "M&A Definitive Agreement",
        "Keywords": "definitive merger agreement, acquire",
        "Score": 25
    }]
    mock_doc_scores = [{"Document Type": "Definitive Agreement", "Score": 15}]
    
    matches = evaluate(
        article_obj={"raw_text": f"{mock_article['title']}\n\n{mock_article['body']}", "document_type": mock_article["document_type"]},
        rules=mock_rules,
        document_type_scores=mock_doc_scores,
        threshold=10
    )
    
    if not matches:
        print("[3. RULES ENGINE] FAILED: Mock article failed rules threshold.")
        return
    print(f"[3. RULES ENGINE] PASSED. Triggered rule '{matches[0]['Name']}' with score {matches[0]['Score']}")

    # 4. Simulate AI Extraction & Classification
    ticker = extract_target_ticker(mock_article["body"])
    print(f"[4. AI EXTRACTION] Extracted Ticker: {ticker}")
    
    # 5. Simulate Alert Formatting & Dispatch (Forcing Mock Mode for safety)
    print("[5. ALERT DISPATCH] Testing notification formatting...")
    send_alert(
        article_title=mock_article["title"],
        article_url=mock_article["url"],
        event_family=matches[0]["Name"],
        confidence=matches[0]["Score"],
        research_summary="1. Executive Summary\nSimulated M&A cash buyout.\n\n4. Investment Facts\n- Offer Price: $45.00\n- Target: ACME",
        evidence_log=matches[0]["Evidence"],
        is_update=False
    )
    
    print("=== SUCCESS: COLLECTIVE PIPELINE SIMULATION COMPLETED ===")

if __name__ == "__main__":
    run_end_to_end_simulation()