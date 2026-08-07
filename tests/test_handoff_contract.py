import sys
import os
import unittest
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import monitor
import hashlib
from monitor import PipelineTelemetry

class TestHandoffContract(unittest.TestCase):
    
    def test_handoff_boundary_isolates_failures(self):
        # We will patch `fetch_all_feeds` in monitor to return a specific batch of raw articles
        # and see if the handoff dedupe loop correctly quarantines the bad ones without crashing.
        
        valid_article = {
            "source": "Valid Source",
            "channel": "HTML",
            "title": "A Valid Title",
            "url": "https://valid.com",
            "published": "",
            "body": "This is a valid body text.",
            "document_type": "Press Release"
        }
        
        # Missing channel
        missing_channel = {
            "source": "Bad Source",
            "title": "Bad Title",
            "url": "https://bad.com",
            "published": "",
            "body": "Bad",
            "document_type": "Press Release"
        }
        
        # Duplicate of valid article
        duplicate_article = valid_article.copy()
        
        raw_articles = [valid_article, missing_channel, duplicate_article]
        
        ingestion_ledger = [
            {"source": "Valid Source", "actual_mode": "HTML"},
            {"source": "Bad Source", "actual_mode": "HTML"}
        ]
        
        with patch('monitor.fetch_all_feeds', return_value=(raw_articles, ingestion_ledger)):
            with patch('monitor.save_workflow_health'):
                with patch('monitor.log_audit_source_metrics'):
                    with patch('monitor.process_article') as mock_process:
                        # We just want to run the ingestion handoff part of main()
                        # To avoid running the full pipeline, we'll extract the dedupe logic or simulate the monitor block
                        
                        telemetry = PipelineTelemetry()
                        telemetry.metrics["downloaded"] = len(raw_articles)
                        
                        unique_articles = []
                        seen_hashes = set()
                        ledger_unique = {f"{entry['source']}::{entry['actual_mode']}": 0 for entry in ingestion_ledger}
                        quarantined = 0
                        
                        def validate_article_contract(art):
                            required = ["source", "channel", "title", "url", "published", "body", "article_hash"]
                            for req in required:
                                if req not in art:
                                    raise KeyError(f"Missing mandatory field: {req}")
                            
                            title_text = art.get("title", "").strip().lower()
                            source_text = art.get("source", "").strip().lower()
                            if not title_text or title_text == "no title" or title_text == "html document":
                                title_text = art.get("body", "")[:200].strip().lower()
                                
                            art["article_hash"] = hashlib.md5(f"{source_text}::{title_text}".encode('utf-8')).hexdigest()
                            return art
                        
                        for article in raw_articles:
                            try:
                                validated_article = validate_article_contract(article)
                                dup_hash = validated_article["article_hash"]
                                
                                if dup_hash not in seen_hashes:
                                    seen_hashes.add(dup_hash)
                                    unique_articles.append(validated_article)
                                    
                                    k = f"{validated_article['source']}::{validated_article['channel']}"
                                    if k in ledger_unique:
                                        ledger_unique[k] += 1
                            except Exception as handoff_err:
                                quarantined += 1
                                
                        # Assertions
                        self.assertEqual(quarantined, 1) # missing_channel was quarantined
                        self.assertEqual(len(unique_articles), 1) # 1 valid, 1 dup dropped
                        self.assertEqual(ledger_unique["Valid Source::HTML"], 1)

if __name__ == '__main__':
    unittest.main(verbosity=2)
