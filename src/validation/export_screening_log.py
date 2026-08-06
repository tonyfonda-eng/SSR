import json
import sqlite3
import os

RESEARCH_DB_PATH = "ssr_observability.db"

def _dict_factory(cursor, row):
    d = {}
    for idx, col in enumerate(cursor.description):
        d[col[0]] = row[idx]
    return d

def export_screening_log(filepath="docs/screening_log.json", limit=1000):
    """
    Exports the most recent N screened articles (passed AND dropped) so the
    dashboard can show exactly what the pipeline looked at and what happened to it.
    Pure display export — never touches pipeline behavior or filtering.
    """
    try:
        conn = sqlite3.connect(RESEARCH_DB_PATH)
        conn.row_factory = _dict_factory
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, run_id, timestamp, headline, url, source, outcome, final_stage, drop_reason, ticker, company_name, event_family, ingestion_mode
            FROM article_screening_log
            ORDER BY timestamp DESC, id DESC
            LIMIT ?
        """, (limit,))
        rows = cursor.fetchall()
        rows = rows[:1000]
        conn.close()

        os.makedirs(os.path.dirname(os.path.abspath(filepath)), exist_ok=True)
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump({"screening_log": rows}, f, indent=2)

        print(f"[EXPORT] Successfully wrote {len(rows)} screening log entries to {filepath}")
        return True
    except Exception as e:
        print(f"[EXPORT ERROR] Failed to generate screening_log.json: {e}")
        return False

if __name__ == "__main__":
    export_screening_log()