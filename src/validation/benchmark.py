import sqlite3
import sys
import os
from datetime import datetime
import statistics

VAL_DB_PATH = "validation.db"
REPORT_PATH = "docs/BENCHMARK_REPORT.md"

def init_benchmark_db():
    """Initializes the latency benchmarking schema."""
    conn = sqlite3.connect(VAL_DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS benchmark_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ticker TEXT,
            source TEXT,
            url TEXT,
            announcement_time DATETIME,
            ssr_detection_time DATETIME,
            delay_seconds INTEGER,
            missed_yn TEXT DEFAULT 'N',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );
    """)
    conn.commit()
    conn.close()

def add_benchmark_record(ticker, source, url, ann_time_str, ssr_time_str="MISSED"):
    """
    Logs an event to calculate SSR detection latency.
    Accepts time in 'YYYY-MM-DD HH:MM:SS' format. Use 'MISSED' if SSR failed to detect.
    """
    # STRICT CONSTRAINT: Never scrape or benchmark Bloomberg.
    if "bloomberg" in source.lower() or "bloomberg.com" in url.lower():
        print(f"[VQA ERROR] Hard constraint violated. Bloomberg sources are strictly prohibited. Record rejected.")
        return

    init_benchmark_db()
    
    ann_time = datetime.strptime(ann_time_str, "%Y-%m-%d %H:%M:%S")
    
    if ssr_time_str.upper() == "MISSED":
        ssr_time = None
        delay_sec = None
        missed = 'Y'
    else:
        ssr_time = datetime.strptime(ssr_time_str, "%Y-%m-%d %H:%M:%S")
        delay_sec = int((ssr_time - ann_time).total_seconds())
        missed = 'N'

    conn = sqlite3.connect(VAL_DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO benchmark_events (ticker, source, url, announcement_time, ssr_detection_time, delay_seconds, missed_yn)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (ticker, source, url, ann_time_str, ssr_time_str if not missed == 'Y' else None, delay_sec, missed))
    
    conn.commit()
    new_id = cursor.lastrowid
    conn.close()
    
    status = f"Missed (Dropped)" if missed == 'Y' else f"Detected in {delay_sec}s"
    print(f"[VQA] Benchmark logged (ID: {new_id}) | {ticker} | {status}")

def generate_benchmark_report():
    """Calculates aggregate lead times and generates the markdown report."""
    init_benchmark_db()
    os.makedirs(os.path.dirname(REPORT_PATH), exist_ok=True)
    
    conn = sqlite3.connect(VAL_DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("SELECT ticker, announcement_time, ssr_detection_time, delay_seconds, missed_yn FROM benchmark_events ORDER BY id DESC")
    records = cursor.fetchall()
    conn.close()

    if not records:
        print("[VQA] No benchmark records found. Add records first.")
        return

    # Calculate Metrics
    delays = [r[3] for r in records if r[3] is not None]
    total_events = len(records)
    missed_count = sum(1 for r in records if r[4] == 'Y')
    
    if delays:
        avg_delay_sec = statistics.mean(delays)
        med_delay_sec = statistics.median(delays)
        avg_lead_mins = round(avg_delay_sec / 60, 2)
        med_lead_mins = round(med_delay_sec / 60, 2)
    else:
        avg_lead_mins = med_lead_mins = 0.0

    date_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        f.write("# SSR Pipeline: Latency & Lead Time Benchmarks\n")
        f.write(f"*Last Updated: {date_str}*\n\n")
        
        f.write("## ⏱️ Aggregate Detection Metrics\n")
        f.write(f"- **Total Benchmarked Events:** {total_events}\n")
        f.write(f"- **Missed Events:** {missed_count}\n")
        f.write(f"- **Average Lead Time (Delay):** {avg_lead_mins} minutes\n")
        f.write(f"- **Median Lead Time (Delay):** {med_lead_mins} minutes\n\n")
        f.write("---\n\n")
        
        f.write("## 📝 Individual Event Records\n\n")
        f.write("| Ticker | Announcement Time | SSR Detection Time | Delay | Missed? |\n")
        f.write("|--------|-------------------|--------------------|-------|---------|\n")
        
        for r in records:
            ticker, ann, ssr, delay, missed = r
            ssr_display = ssr if ssr else "--"
            delay_display = f"{round(delay / 60, 2)}m" if delay is not None else "--"
            miss_display = "🔴 YES" if missed == 'Y' else "🟢 NO"
            f.write(f"| **{ticker}** | `{ann}` | `{ssr_display}` | {delay_display} | {miss_display} |\n")

    print(f"[VQA] Benchmark report compiled cleanly to {REPORT_PATH}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python3 -m src.validation.benchmark add <ticker> <source> <url> \"YYYY-MM-DD HH:MM:SS\" \"YYYY-MM-DD HH:MM:SS\"")
        print("  python3 -m src.validation.benchmark add <ticker> <source> <url> \"YYYY-MM-DD HH:MM:SS\" MISSED")
        print("  python3 -m src.validation.benchmark report")
        sys.exit(1)
        
    command = sys.argv[1].lower()
    
    if command == "add":
        if len(sys.argv) >= 6:
            ssr_time = sys.argv[6] if len(sys.argv) == 7 else "MISSED"
            add_benchmark_record(sys.argv[2], sys.argv[3], sys.argv[4], sys.argv[5], ssr_time)
        else:
            print("[VQA ERROR] Missing arguments for 'add'.")
    elif command == "report":
        generate_benchmark_report()
    else:
        print("Invalid arguments.")
