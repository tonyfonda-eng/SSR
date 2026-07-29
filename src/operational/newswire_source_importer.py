import logging
from typing import List
from urllib.parse import urlparse
from src.app.ingestion.newswire_models import NewswireSource

logger = logging.getLogger("SSR.NewswireSourceImporter")

class NewswireSourceImporter:
    """Parses and validates dynamic newswire configurations from Google Sheets."""
    
    def __init__(self, spreadsheet_client):
        self.client = spreadsheet_client
        self.sheet_name = "09_Newswire_Sources"

    def load_enabled_sources(self, spreadsheet_id: str) -> List[NewswireSource]:
        enabled_sources = []
        try:
            # Fetch raw matrix payload from the dedicated worksheet
            raw_records = self.client.get_sheet_records(spreadsheet_id, self.sheet_name)
        except Exception as e:
            logger.error(f"Failed to pull sheet {self.sheet_name}. Falling back to defaults. Error: {e}")
            return []

        for row in raw_records:
            # 1. Enforce strict enablement constraint
            enabled_str = str(row.get("Enabled", "")).strip().lower()
            if enabled_str not in ("true", "1", "yes"):
                continue

            source_id = str(row.get("Source_ID", "")).strip()
            name = str(row.get("Source_Name", "")).strip()
            url = str(row.get("Feed_URL", "")).strip()
            
            # 2. Strict URL validation boundary
            parsed_url = urlparse(url)
            if not parsed_url.scheme or not parsed_url.netloc:
                logger.warning(f"Rejected invalid or malformed Feed_URL for Source_ID {source_id}: '{url}'")
                continue

            try:
                interval = int(row.get("Poll_Interval_Minutes", 15))
            except (ValueError, TypeError):
                interval = 15

            tags = [t.strip() for t in str(row.get("Tags", "")).split(",") if t.strip()]

            source = NewswireSource(
                source_id=source_id,
                source_name=name,
                feed_url=url,
                publisher=str(row.get("Publisher", "")).strip(),
                category=str(row.get("Category", "")).strip(),
                poll_interval_minutes=interval,
                tags=tags,
                notes=str(row.get("Notes", "")).strip()
            )
            enabled_sources.append(source)

        logger.info(f"Successfully loaded {len(enabled_sources)} dynamic newswire targets from spreadsheet.")
        return enabled_sources
