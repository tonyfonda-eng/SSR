import sys
import os
import unittest
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.ingestion.scrapers import _fetch_html_channel, _fetch_rss_channel
from src.scrapers.prnewswire import PRNewsWireScraper
from src.scrapers.businesswire import BusinessWireScraper

class TestIngestionContract(unittest.TestCase):
    
    def test_1_zero_previous_checkpoint(self):
        source = {"Source Name": "PR Newswire", "Type": "HTML Parsing", "Target URL": "https://www.prnewswire.com"}
        with patch('src.ingestion.scrapers.get_checkpoint', return_value=None):
            with patch('src.ingestion.scrapers.set_checkpoint') as mock_set:
                articles, ledger, _ = _fetch_html_channel(source)
                self.assertEqual(ledger["recovery_status"], "NOT_REQUIRED")
                self.assertTrue(mock_set.called)

    def test_2_checkpoint_present_in_rss(self):
        source = {"Source Name": "PR Newswire", "Type": "HTML Parsing", "Target URL": "https://www.prnewswire.com"}
        prn_scraper = PRNewsWireScraper()
        arts = prn_scraper.get_latest_articles(checkpoint=None)
        recent_cp = arts[1]["url"] if len(arts) > 1 else "fake"
        
        with patch('src.ingestion.scrapers.get_checkpoint', return_value=recent_cp):
            with patch('src.ingestion.scrapers.set_checkpoint') as mock_set:
                articles, ledger, _ = _fetch_html_channel(source)
                self.assertEqual(ledger["recovery_status"], "NOT_REQUIRED")
                if len(arts) > 1:
                    self.assertTrue(mock_set.called)

    def test_3_4_missing_checkpoint_recovers(self):
        source = {"Source Name": "PR Newswire", "Type": "HTML Parsing", "Target URL": "https://www.prnewswire.com"}
        with patch('bs4.BeautifulSoup') as mock_bs:
            mock_soup = MagicMock()
            mock_bs.return_value = mock_soup
            fake_item_1 = MagicMock()
            fake_item_1.get.return_value = "https://www.prnewswire.com/news-releases/older-article.html"
            fake_item_1.select_one.return_value = MagicMock(text="Fake Title 1")
            
            fake_item_2 = MagicMock()
            fake_item_2.get.return_value = "https://www.prnewswire.com/news-releases/target-checkpoint.html"
            fake_item_2.select_one.return_value = MagicMock(text="Fake Title 2")
            
            mock_soup.select.return_value = [fake_item_1, fake_item_2]
            
            with patch('src.ingestion.scrapers.get_checkpoint', return_value="https://www.prnewswire.com/news-releases/target-checkpoint.html"):
                with patch('src.ingestion.scrapers.set_checkpoint') as mock_set:
                    with patch('src.scrapers.prnewswire.requests.get') as mock_get:
                        mock_resp = MagicMock()
                        mock_resp.status_code = 200
                        mock_get.return_value = mock_resp
                        
                        articles, ledger, _ = _fetch_html_channel(source)
                        self.assertEqual(ledger["recovery_status"], "RECOVERED")
                        self.assertTrue(mock_set.called)

    def test_5_backfill_hits_limit(self):
        source = {"Source Name": "PR Newswire", "Type": "HTML Parsing", "Target URL": "https://www.prnewswire.com", "max_backfill_pages": 1}
        with patch('src.ingestion.scrapers.get_checkpoint', return_value="impossible_checkpoint"):
            with patch('src.ingestion.scrapers.set_checkpoint') as mock_set:
                with patch('bs4.BeautifulSoup') as mock_bs:
                    mock_soup = MagicMock()
                    mock_bs.return_value = mock_soup
                    fake_item = MagicMock()
                    fake_item.get.return_value = "https://www.prnewswire.com/news-releases/never-ending.html"
                    fake_item.select_one.return_value = MagicMock(text="Fake Title")
                    mock_soup.select.return_value = [fake_item]
                    
                    with patch('src.scrapers.prnewswire.requests.get') as mock_get:
                        mock_resp = MagicMock()
                        mock_resp.status_code = 200
                        mock_get.return_value = mock_resp
                        
                        articles, ledger, _ = _fetch_html_channel(source)
                        self.assertEqual(ledger["status"], "GAP_DETECTED")
                        self.assertFalse(mock_set.called)

    def test_6_business_wire_403(self):
        source = {"Source Name": "Business Wire", "Type": "RSS", "Target URL": "https://www.businesswire.com"}
        with patch('src.ingestion.scrapers.get_checkpoint', return_value="impossible_id"):
            with patch('src.ingestion.scrapers.set_checkpoint') as mock_set:
                with patch('src.scrapers.businesswire.feedparser.parse') as mock_feed:
                    mock_entry = MagicMock()
                    mock_entry.link = "https://www.businesswire.com/news/home/20260101/en/"
                    mock_feed.return_value = MagicMock(entries=[mock_entry])
                    
                    with patch('src.scrapers.businesswire.get_session') as mock_session:
                        mock_resp = MagicMock()
                        mock_resp.status_code = 200
                        mock_resp.content = b""
                        mock_session.return_value.get.return_value = mock_resp
                        
                        articles, ledger, _ = _fetch_html_channel(source)
                        self.assertEqual(ledger["status"], "GAP_DETECTED")
                        self.assertEqual(ledger["recovery_status"], "BLOCKED")
                        self.assertFalse(mock_set.called)

    def test_7_network_exception_failed(self):
        source = {"Source Name": "PR Newswire", "Type": "HTML Parsing", "Target URL": "https://www.prnewswire.com"}
        with patch('src.ingestion.scrapers.get_checkpoint', return_value="impossible"):
            with patch('src.ingestion.scrapers.set_checkpoint') as mock_set:
                with patch('src.scrapers.prnewswire.requests.get', side_effect=Exception("Timeout")):
                    articles, ledger, _ = _fetch_html_channel(source)
                    self.assertEqual(ledger["recovery_status"], "FAILED")
                    self.assertFalse(mock_set.called)

    def test_8_retry_after_gap(self):
        source = {"Source Name": "PR Newswire", "Type": "HTML Parsing", "Target URL": "https://www.prnewswire.com"}
        with patch('bs4.BeautifulSoup') as mock_bs:
            mock_soup = MagicMock()
            mock_bs.return_value = mock_soup
            
            fake_new = MagicMock()
            fake_new.get.return_value = "https://www.prnewswire.com/news-releases/newer.html"
            fake_new.select_one.return_value = MagicMock(text="Newer Title")
            
            fake_item_1 = MagicMock()
            fake_item_1.get.return_value = "https://www.prnewswire.com/news-releases/target-checkpoint.html"
            fake_item_1.select_one.return_value = MagicMock(text="Target Title")
            
            mock_soup.select.return_value = [fake_new, fake_item_1]
            
            with patch('src.ingestion.scrapers.get_checkpoint', return_value="https://www.prnewswire.com/news-releases/target-checkpoint.html"):
                with patch('src.ingestion.scrapers.set_checkpoint') as mock_set:
                    with patch('src.scrapers.prnewswire.requests.get') as mock_get:
                        mock_resp = MagicMock()
                        mock_resp.status_code = 200
                        mock_get.return_value = mock_resp
                        articles, ledger, _ = _fetch_html_channel(source)
                        self.assertEqual(ledger["recovery_status"], "RECOVERED")
                        self.assertTrue(mock_set.called)

    def test_9_transactional_checkpoint(self):
        # A downstream error (in this test, simulating get_article_body crash)
        source = {"Source Name": "PR Newswire", "Type": "HTML Parsing", "Target URL": "https://www.prnewswire.com"}
        with patch('src.ingestion.scrapers.get_checkpoint', return_value=None):
            with patch('src.ingestion.scrapers.set_checkpoint') as mock_set:
                # Mock PRNewsWireScraper.get_article_body to crash entirely
                # Actually, the orchestrator catches get_article_body crashes per article and ignores them.
                # So we simulate a full get_latest_articles crash.
                with patch('src.scrapers.prnewswire.PRNewsWireScraper.get_latest_articles', side_effect=Exception("Crash!")):
                    articles, ledger, _ = _fetch_html_channel(source)
                    self.assertFalse(mock_set.called)
                    self.assertEqual(ledger["recovery_status"], "FAILED")

    def test_10_config_drift(self):
        source = {"Source Name": "PR Newswire", "Type": "RSS", "Target URL": "https://www.prnewswire.com"}
        with patch('src.ingestion.scrapers.get_checkpoint', return_value=None):
            with patch('src.scrapers.prnewswire.PRNewsWireScraper.get_latest_articles', return_value=[]):
                articles, ledger, _ = _fetch_html_channel(source)
                self.assertTrue(ledger["config_drift"])
                self.assertEqual(ledger["configured_mode"], "RSS")
                self.assertEqual(ledger["actual_mode"], "HTML")

if __name__ == '__main__':
    unittest.main(verbosity=2)

    def test_13_partial_body_failure_does_not_advance_checkpoint(self):
        source = {"Source Name": "PR Newswire", "Type": "HTML Parsing", "Target URL": "https://www.prnewswire.com"}
        with patch('src.ingestion.scrapers.get_checkpoint', return_value="https://www.prnewswire.com/news-releases/target-checkpoint.html"):
            with patch('src.ingestion.scrapers.set_checkpoint') as mock_set:
                with patch('src.scrapers.prnewswire.PRNewsWireScraper.get_latest_articles') as mock_latest:
                    # Return two fake articles
                    mock_latest.return_value = [
                        {"url": "https://www.prnewswire.com/news-releases/article-1.html", "title": "A1"},
                        {"url": "https://www.prnewswire.com/news-releases/article-2.html", "title": "A2"}
                    ]
                    
                    # Mock scrape_metadata
                    with patch('src.scrapers.prnewswire.PRNewsWireScraper.scrape_metadata', new_callable=dict) as mock_meta:
                        mock_meta["recovery_status"] = "NOT_REQUIRED"
                        mock_meta["checkpoint_found"] = True
                        
                        # Mock get_article_body to fail on the second article
                        with patch('src.scrapers.prnewswire.PRNewsWireScraper.get_article_body', side_effect=[
                            "Body 1 is quite long and succeeds...", 
                            Exception("Network timeout during body fetch")
                        ]):
                            articles, ledger, _ = _fetch_html_channel(source)
                            
                            self.assertEqual(ledger["status"], "FAILED")
                            self.assertEqual(ledger["health"], "DEGRADED")
                            self.assertTrue(ledger["checkpoint_frozen"])
                            self.assertFalse(mock_set.called)

