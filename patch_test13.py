import re

with open('tests/test_ingestion_contract.py', 'r') as f:
    content = f.read()

target = """    def test_13_partial_body_failure_does_not_advance_checkpoint(self):
        source = {"Source Name": "PR Newswire", "Type": "HTML Parsing", "Target URL": "https://www.prnewswire.com"}
        with patch('src.ingestion.scrapers.get_checkpoint', return_value="https://www.prnewswire.com/news-releases/target-checkpoint.html"):
            with patch('src.ingestion.scrapers.set_checkpoint') as mock_set:
                with patch('src.ingestion.scrapers.get_scraper_for_source') as mock_get_scraper:
                    mock_scraper = MagicMock()
                    mock_scraper.get_latest_articles.return_value = [
                        {"url": "https://www.prnewswire.com/news-releases/article-1.html", "title": "A1"},
                        {"url": "https://www.prnewswire.com/news-releases/article-2.html", "title": "A2"}
                    ]
                    mock_scraper.scrape_metadata = {
                        "recovery_status": "NOT_REQUIRED",
                        "checkpoint_found": True
                    }
                    mock_scraper.get_article_body.side_effect = [
                        "Body 1 is quite long and succeeds...", 
                        Exception("Network timeout during body fetch")
                    ]
                    mock_get_scraper.return_value = mock_scraper
                    
                    articles, ledger, _ = _fetch_html_channel(source)
                    
                    self.assertEqual(ledger["status"], "FAILED")
                    self.assertEqual(ledger["health"], "DEGRADED")
                    self.assertTrue(ledger["checkpoint_frozen"])
                    self.assertFalse(mock_set.called)"""

content = re.sub(r'    def test_13_partial_body_failure_does_not_advance_checkpoint\(self\):.*?self\.assertFalse\(mock_set\.called\)', target, content, flags=re.DOTALL)

with open('tests/test_ingestion_contract.py', 'w') as f:
    f.write(content)
