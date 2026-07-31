import requests
from bs4 import BeautifulSoup
import PyPDF2
import io
import os
import re
from src.alerts.email import send_alert
from src.scrapers.base import SourceScraper


class KEDMScraper(SourceScraper):

    def _login_and_get_session(self):
        # Credentials MUST come from environment variables — no hardcoded defaults
        username = os.environ.get("KEDM_USER")
        password = os.environ.get("KEDM_PASS")

        if not username or not password:
            print("[WARNING] KEDM_USER or KEDM_PASS not set. Skipping KEDM ingestion.")
            return None

        s = requests.Session()
        r = s.get('https://kedm.com/my-account/')
        soup = BeautifulSoup(r.text, 'html.parser')

        login_data = {
            'username': username,
            'password': password,
            'login': 'Log in'
        }

        form = soup.find('form', class_='woocommerce-form-login')
        if form:
            for inp in form.find_all('input', type='hidden'):
                login_data[inp.get('name')] = inp.get('value')

        s.post('https://kedm.com/my-account/', data=login_data)
        return s

    def get_latest_articles(self):
        """
        Returns a list of dicts representing the latest KEDM reports.
        """
        articles = []
        try:
            s = self._login_and_get_session()
            if s is None:
                return articles

            r = s.get('https://kedm.com/archives/')
            soup = BeautifulSoup(r.text, 'html.parser')

            # Find all download buttons
            links = soup.find_all('a', href=re.compile(r'smd_process_download=1'))

            flag_file = "/tmp/kedm_expired.flag"
            if not links:
                print("[WARNING] No download links found on KEDM Archives. Trial likely expired.")
                if not os.path.exists(flag_file):
                    send_alert(
                        article_title="ACTION REQUIRED: KEDM Trial Expired",
                        article_url="https://kedm.com/my-account/",
                        event_family="SYSTEM ALERT",
                        confidence=100,
                        research_summary="Your KEDM free trial appears to have expired. The pipeline logged in but found no download links. Please register a new email and update KEDM_USER / KEDM_PASS.",
                        evidence_log=[],
                        is_update=False
                    )
                    open(flag_file, 'a').close()
                return articles

            # If we got links, clear the flag if it exists
            if os.path.exists(flag_file):
                os.remove(flag_file)

            # Just process the most recent 3 to avoid overloading
            for a in links[:3]:
                url = a.get('href')
                # Extract download ID to use as unique article ID
                match = re.search(r'download_id=(\d+)', url)
                if not match:
                    continue

                article_id = match.group(1)
                title = f"KEDM Report {article_id}"

                # Look for the title in the DOM (usually near the button)
                parent = a.find_parent('div', class_='report_thumbnail')
                if parent:
                    h4 = parent.find('h4')
                    if h4:
                        title = h4.text.strip()

                articles.append({
                    'id': article_id,
                    'title': title,
                    'url': url,
                    'published': '',  # Date is often in title, can parse later
                    'body': None  # Body fetched lazily to save bandwidth
                })

        except Exception as e:
            print(f"[ERROR] KEDM Scraper Failed: {e}")

        return articles

    def get_article_body(self, url):
        """
        Downloads the PDF from the smd_process_download URL and extracts text.
        """
        try:
            s = self._login_and_get_session()
            if s is None:
                return ""

            r = s.get(url)

            if r.status_code != 200:
                return ""

            reader = PyPDF2.PdfReader(io.BytesIO(r.content))
            text = ""
            for page in reader.pages:
                text += page.extract_text() + "\n"
            return text
        except Exception as e:
            print(f"[ERROR] KEDM PDF Extraction Failed: {e}")
            return ""
