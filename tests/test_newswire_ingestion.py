import pytest
from unittest.mock import MagicMock
from src.operational.newswire_source_importer import NewswireSourceImporter

def test_importer_filters_enabled_and_validates_urls():
    mock_client = MagicMock()
    mock_client.get_sheet_records.return_value = [
        {"Source_ID": "S1", "Enabled": "TRUE", "Source_Name": "Valid Feed", "Feed_URL": "https://valid.com/rss", "Poll_Interval_Minutes": "15"},
        {"Source_ID": "S2", "Enabled": "FALSE", "Source_Name": "Disabled Feed", "Feed_URL": "https://disabled.com/rss"},
        {"Source_ID": "S3", "Enabled": "TRUE", "Source_Name": "Bad Feed", "Feed_URL": "not-a-valid-url"}
    ]
    
    importer = NewswireSourceImporter(mock_client)
    sources = importer.load_enabled_sources("mock_sheet_id")
    
    assert len(sources) == 1
    assert sources[0].source_id == "S1"
    assert sources[0].feed_url == "https://valid.com/rss"

print("Ingestion test criteria written.")
