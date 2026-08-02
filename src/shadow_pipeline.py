import sqlite3
import json

def log_to_shadow_pipeline(article_data, failed_rule_id, db_path="shadow_review.sqlite"):
    """
    Writes rules-rejected articles to a dedicated shadow database 
    for weekly AI review, ensuring no opportunities are silently missed.
    """
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS shadow_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                failed_rule_id TEXT,
                article_json TEXT
            );
        """)
        cursor.execute(
            "INSERT INTO shadow_log (failed_rule_id, article_json) VALUES (?, ?)",
            (failed_rule_id, json.dumps(article_data))
        )
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"[SHADOW PIPELINE ERROR] Failed to log article: {e}")
