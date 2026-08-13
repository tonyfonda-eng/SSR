import re

with open('tests/test_ingestion_contract.py', 'r') as f:
    content = f.read()

# Fix test_2
target_2 = """    def test_2_checkpoint_present_in_rss(self):
        source = {"Source Name": "PR Newswire", "Type": "HTML Parsing", "Target URL": "https://www.prnewswire.com"}
        prn_scraper = PRNewsWireScraper()
        arts = prn_scraper.get_latest_articles(checkpoint=None)
        recent_cp = arts[1]["url"] if len(arts) > 1 else "fake"
        
        with patch('src.ingestion.scrapers.get_checkpoint', return_value=recent_cp):
            with patch('src.ingestion.scrapers.set_checkpoint') as mock_set:
                articles, ledger, _ = _fetch_html_channel(source)
                self.assertEqual(ledger["recovery_status"], "NOT_REQUIRED")
                if len(arts) > 1:
                    self.assertTrue(mock_set.called)"""
                    
content = re.sub(r'    def test_2_checkpoint_present_in_rss\(self\):.*?self\.assertTrue\(mock_set\.called\)', target_2, content, flags=re.DOTALL)

# Fix test_6
target_6 = """    def test_6_business_wire_403(self):
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
                        self.assertFalse(mock_set.called)"""
                        
content = re.sub(r'    def test_6_business_wire_403\(self\):.*?self\.assertFalse\(mock_set\.called\)', target_6, content, flags=re.DOTALL)

# Fix test_8
target_8 = """    def test_8_retry_after_gap(self):
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
                        self.assertTrue(mock_set.called)"""
                        
content = re.sub(r'    def test_8_retry_after_gap\(self\):.*?self\.assertTrue\(mock_set\.called\)', target_8, content, flags=re.DOTALL)

# Fix test_10
target_10 = """    def test_10_config_drift(self):
        source = {"Source Name": "PR Newswire", "Type": "RSS", "Target URL": "https://www.prnewswire.com"}
        with patch('src.ingestion.scrapers.get_checkpoint', return_value=None):
            with patch('src.scrapers.prnewswire.PRNewsWireScraper.get_latest_articles', return_value=[]):
                articles, ledger, _ = _fetch_html_channel(source)
                self.assertTrue(ledger["config_drift"])
                self.assertEqual(ledger["configured_mode"], "RSS")
                self.assertEqual(ledger["actual_mode"], "HTML")"""
                
content = re.sub(r'    def test_10_config_drift\(self\):.*?self\.assertEqual\(ledger\["actual_mode"\], "HTML"\)', target_10, content, flags=re.DOTALL)

with open('tests/test_ingestion_contract.py', 'w') as f:
    f.write(content)
