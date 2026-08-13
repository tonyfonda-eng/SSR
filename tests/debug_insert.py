import sqlite3
import traceback
import hashlib
from monitor import process_article, PipelineTelemetry
from src.database import check_event_exists
from src.ai import ProviderRouter
from tests.test_dedupe_state import get_base_article, get_mock_config
from unittest.mock import patch

orig_execute = sqlite3.Cursor.execute
def mock_execute(self, sql, *args, **kwargs):
    if "INSERT" in sql.upper() and "event_registry" in sql.lower():
        print("BINGO! INSERT DETECTED!")
        traceback.print_stack()
    return orig_execute(self, sql, *args, **kwargs)

sqlite3.Cursor.execute = mock_execute

art = get_base_article("X", "Debug Crash Test")
telemetry = PipelineTelemetry()

with patch('monitor.stage_ontology_concepts', side_effect=ValueError("Simulated Crash")):
    try:
        process_article(art.copy(), telemetry, get_mock_config(), "HASH", ProviderRouter())
    except ValueError:
        pass

conn = sqlite3.connect("ssr_observability.db")
cur = conn.cursor()
cur.execute("SELECT * FROM event_registry WHERE article_hash = ?", (art["article_hash"],))
print("Registry contains:", cur.fetchall())
conn.close()
