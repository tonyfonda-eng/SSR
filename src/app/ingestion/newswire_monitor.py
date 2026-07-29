import logging
import feedparser
import gspread
from urllib.parse import urlparse
from google.oauth2.service_account import Credentials

from src.app.ingestion.newswire_models import NewswireSource
from src.engine.primitives import EventTopic, EventEnvelope, EventMetadata
from src.config.secrets import get_google_service_account
import src.rules_engine as rules_engine

logger = logging.getLogger("SSR.NewswireMonitor")

class NewswireMonitorTask:
    """Iterates dynamically over spreadsheet-backed feeds using native gspread authentication."""

    def __init__(self, config, store, event_bus, spreadsheet_client=None):
        self.config = config
        self.store = store
        self.event_bus = event_bus
        self.fallback_url = "https://www.prnewswire.com/rss/news-releases-list.rss"
        self.scopes = ["https://www.googleapis.com/auth/spreadsheets.readonly"]

    def _get_sheet_client(self):
        """Authenticates using existing secrets infrastructure."""
        credentials = Credentials.from_service_account_info(
            get_google_service_account(),
            scopes=self.scopes,
        )
        return gspread.authorize(credentials)

    def _open_spreadsheet(self, client, sheet_id: str):
        """Helper to open spreadsheet by URL or raw alphanumeric key."""
        if sheet_id.startswith("http"):
            return client.open_by_url(sheet_id)
        return client.open_by_key(sheet_id)

    def _load_sources_from_sheets(self, sheet_id: str) -> list:
        """Pulls and validates rows from the 09_Newswire_Sources tab."""
        enabled_sources = []
        try:
            client = self._get_sheet_client()
            sheet = self._open_spreadsheet(client, sheet_id)
            worksheet = sheet.worksheet("09_Newswire_Sources")
            raw_records = worksheet.get_all_records()
        except Exception as e:
            logger.error(f"Failed to pull worksheet '09_Newswire_Sources'. Activating safety fallbacks. Error: {e}")
            return []

        for row in raw_records:
            enabled_str = str(row.get("Enabled", "")).strip().lower()
            if enabled_str not in ("true", "1", "yes"):
                continue

            source_id = str(row.get("Source_ID", "")).strip()
            name = str(row.get("Source_Name", "")).strip()
            url = str(row.get("Feed_URL", "")).strip()
            
            parsed_url = urlparse(url)
            if not parsed_url.scheme or not parsed_url.netloc:
                logger.warning(f"Skipping malformed feed configuration URL for {source_id}: '{url}'")
                continue

            try:
                interval = int(row.get("Poll_Interval_Minutes", 15))
            except (ValueError, TypeError):
                interval = 15

            enabled_sources.append(NewswireSource(
                source_id=source_id,
                source_name=name,
                feed_url=url,
                publisher=str(row.get("Publisher", "")).strip(),
                category=str(row.get("Category", "")).strip(),
                poll_interval_minutes=interval,
                tags=[t.strip() for t in str(row.get("Tags", "")).split(",") if t.strip()],
                notes=str(row.get("Notes", "")).strip()
            ))
        return enabled_sources

    def execute(self, sheet_id: str) -> None:
        logger.info("Initiating dynamic multi-source newswire ingestion sweep...")
        
        if not sheet_id:
            logger.error("No SSR_SPREADSHEET_ID set in environment variables.")
            return

        sources = self._load_sources_from_sheets(sheet_id)
        
        if not sources:
            logger.warning("No dynamic sources found or sheet inaccessible. Activating fallback safety profile.")
            sources = [NewswireSource("PRN_FALLBACK", "PR Newswire Fallback", self.fallback_url, "Cision", "General", 15)]

        # Fetch and load playbook rules using the authed sheet session helper
        try:
            client = self._get_sheet_client()
            sheet = self._open_spreadsheet(client, sheet_id)
            rules_worksheet = sheet.worksheet("Rules")
            playbooks = rules_worksheet.get_all_records()
        except Exception as e:
            logger.warning(f"Could not extract dynamic rules tab context, using local empty defaults. Error: {e}")
            playbooks = []

        for source in sources:
            logger.info(f"Polling feed target: [{source.source_name}] -> {source.feed_url}")
            try:
                feed = feedparser.parse(source.feed_url)
                
                for entry in feed.entries:
                    title = entry.get("title", "Untitled Article")
                    link = entry.get("link", "")
                    summary = entry.get("summary", "")
                    full_text = f"{title} {summary}"
                    
                    article_payload = {
                        "title": title,
                        "link": link,
                        "summary": summary,
                        "published_raw": entry.get("published", ""),
                        "source_metadata": {
                            "source_id": source.source_id,
                            "source_name": source.source_name,
                            "publisher": source.publisher,
                            "category": source.category,
                            "tags": source.tags
                        }
                    }

                    matches = rules_engine.evaluate(full_text, playbooks)
                    if bool(matches):
                        logger.info(f"Match detected in source [{source.source_name}]: '{title}'")
                        
                        # Fallback topic schema aligned to legacy event bridge definitions
                        envelope = EventEnvelope(
                            metadata=EventMetadata(
                                topic=EventTopic.CALC_RISK_ASSIGNMENT,
                                schema_version="1.1",
                                correlation_id=f"NEWS-{source.source_id}-{hash(link)}"
                            ),
                            payload=type("PayloadObj", (object,), {"ticker": f"NEWSWIRE: {source.source_name}", "result_value": 1.0, "article": article_payload})()
                        )
                        self.event_bus.publish(EventTopic.CALC_RISK_ASSIGNMENT, envelope)

                logger.info(f"Successfully processed {len(feed.entries)} entries for source: {source.source_name}")
                
            except Exception as e:
                logger.error(f"Execution fault occurring during poll of newswire source {source.source_name}: {e}")
