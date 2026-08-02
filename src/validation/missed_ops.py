import sqlite3
import sys
import os
from datetime import datetime

VAL_DB_PATH = "validation.db"
REPORT_PATH = "docs/MISSED_OPPORTUNITIES.md"

def init_db():
    """Ensures the missed_opportunities table exists."""
    conn = sqlite3.connect(VAL_DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS missed_opportunities (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ticker TEXT,
            url TEXT,
            root_cause TEXT,
            status TEXT DEFAULT 'OPEN',
            initial_notes TEXT,
            resolution_notes TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            closed_at DATETIME
        );
    """)
    conn.commit()
    conn.close()

def add_missed(ticker, url, root_cause, notes=""):
    """Logs a newly discovered pipeline failure to the backlog."""
    init_db()
    conn = sqlite3.connect(VAL_DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO missed_opportunities (ticker, url, root_cause, initial_notes)
        VALUES (?, ?, ?, ?)
    """, (ticker, url, root_cause, notes))
    conn.commit()
    new_id = cursor.lastrowid
    conn.close()
    print(f"[VQA] Logged new missed opportunity (ID: {new_id}) for {ticker} | Root Cause: {root_cause}")

def close_missed(record_id, resolution_notes):
    """Marks a missed opportunity as patched and closed."""
    init_db()
    conn = sqlite3.connect(VAL_DB_PATH)
    cursor = conn.cursor()
    
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    cursor.execute("""
        UPDATE missed_opportunities 
        SET status = 'CLOSED', resolution_notes = ?, closed_at = ? 
        WHERE id = ?
    """, (resolution_notes, timestamp, record_id))
    
    if cursor.rowcount == 0:
        print(f"[VQA ERROR] Record ID {record_id} not found.")
    else:
        print(f"[VQA] Closed Missed Opportunity ID {record_id}.")
        
    conn.commit()
    conn.close()

def report_missed():
    """Generates the docs/MISSED_OPPORTUNITIES.md report."""
    init_db()
    os.makedirs(os.path.dirname(REPORT_PATH), exist_ok=True)
    
    conn = sqlite3.connect(VAL_DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("SELECT id, ticker, url, root_cause, initial_notes, created_at FROM missed_opportunities WHERE status = 'OPEN' ORDER BY id DESC")
    open_records = cursor.fetchall()
    
    cursor.execute("SELECT id, ticker, root_cause, resolution_notes, closed_at FROM missed_opportunities WHERE status = 'CLOSED' ORDER BY closed_at DESC LIMIT 50")
    closed_records = cursor.fetchall()
    
    conn.close()

    date_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        f.write("# SSR Pipeline: Missed Opportunities Backlog\n")
        f.write(f"*Last Updated: {date_str}*\n\n")
        
        f.write(f"**Open Issues:** {len(open_records)} | **Recently Closed:** {len(closed_records)}\n\n")
        f.write("---\n\n")
        
        f.write("## 🔴 Action Required: Open Misses\n\n")
        if open_records:
            f.write("| ID | Ticker | Root Cause | Target URL | Notes | Date Logged |\n")
            f.write("|---|--------|------------|------------|-------|-------------|\n")
            for r in open_records:
                f.write(f"| {r[0]} | **{r[1]}** | `{r[3]}` | [Link]({r[2]}) | {r[4]} | {r[5][:10]} |\n")
        else:
            f.write("*Pipeline is clean. No open misses currently tracked.*\n")
            
        f.write("\n---\n\n")
        
        f.write("## 🟢 Resolved: Recently Closed\n\n")
        if closed_records:
            f.write("| ID | Ticker | Root Cause | Resolution Notes | Date Closed |\n")
            f.write("|---|--------|------------|------------------|-------------|\n")
            for r in closed_records:
                f.write(f"| {r[0]} | **{r[1]}** | `{r[2]}` | {r[3]} | {r[4][:10]} |\n")
        else:
            f.write("*No resolved misses yet.*\n")

    print(f"[VQA] Missed Opportunities report generated successfully at {REPORT_PATH}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python3 -m src.validation.missed_ops add <ticker> <url> <root_cause> \"<notes>\"")
        print("  python3 -m src.validation.missed_ops close <id> \"<resolution_notes>\"")
        print("  python3 -m src.validation.missed_ops report")
        sys.exit(1)
        
    command = sys.argv[1].lower()
    
    if command == "add" and len(sys.argv) >= 5:
        notes = sys.argv[5] if len(sys.argv) > 5 else ""
        add_missed(sys.argv[2], sys.argv[3], sys.argv[4], notes)
    elif command == "close" and len(sys.argv) >= 4:
        close_missed(sys.argv[2], sys.argv[3])
    elif command == "report":
        report_missed()
    else:
        print("Invalid arguments.")
