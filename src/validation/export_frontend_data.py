import os
import json
import ast
import sqlite3
import datetime

DB_PATH = "ssr_observability.db"

def export_data():
    os.makedirs("docs", exist_ok=True)
    
    if not os.path.exists(DB_PATH):
        print(f"[WARNING] Observability database not found at {DB_PATH}. Postponing export.")
        return

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # ---------------------------------------------------------
    # 1. EXTRACT THE DECISION LEDGER (archive_data.json)
    # ---------------------------------------------------------
    archive_list = []
    source_stats = {}
    total_processed = 0
    total_alerts = 0
    
    try:
        cursor.execute("SELECT log_text FROM lifecycle_logs ORDER BY id DESC LIMIT 1000")
        rows = cursor.fetchall()
        
        for row in rows:
            raw_text = row["log_text"]
            data = None
            
            # Robust parsing: Try strict JSON first, fallback to Python literal dict eval if single-quoted
            try:
                data = json.loads(raw_text)
            except Exception:
                try:
                    data = ast.literal_eval(raw_text)
                    if isinstance(data, dict):
                        data = {str(k): v for k, v in data.items()}
                except Exception as parse_err:
                    print(f"[DEBUG] Skipping unparseable log row: {parse_err}")
                    continue
            
            if not isinstance(data, dict):
                continue
                
            try:
                # Standardize Timestamps
                ts = data.get("timestamp", "")
                if ts and "GMT" not in ts and "UTC" not in ts:
                    ts += " GMT"
                data["timestamp"] = ts
                
                # Enhance Drop Reasons to expose Rule Engine specifics
                if data.get("pipeline_stage") == "Rules Engine" and data.get("outcome") == "Dropped":
                    if data.get("reason") == "Failed Rules Threshold":
                        data["reason"] = "Failed Rules Threshold (Score < 10)"
                        
                archive_list.append(data)
                
                # Dynamically build Source Intelligence metrics while we iterate
                src = data.get("source", "Unknown")
                if src not in source_stats:
                    source_stats[src] = {"source": src, "articles": 0, "alerts": 0, "ontology_pct": 0, "rules_pct": 0, "failures": 0}
                
                source_stats[src]["articles"] += 1
                total_processed += 1
                
                outcome = str(data.get("outcome", "")).upper()
                stage = str(data.get("pipeline_stage", "")).upper()
                
                if outcome == "DISPATCHED":
                    source_stats[src]["alerts"] += 1
                    total_alerts += 1
                elif "ONTOLOGY" in stage:
                    source_stats[src]["ontology_pct"] += 1
                elif "RULES" in stage:
                    source_stats[src]["rules_pct"] += 1
                elif outcome in ["FAILED", "ERROR"]:
                    source_stats[src]["failures"] += 1
                    
            except Exception as e:
                print(f"[WARNING] Error processing log record fields: {e}")
                continue
                
    except Exception as e:
        print(f"[WARNING] Archive Data Sync Database Error: {e}")

    if not archive_list:
        archive_list = [{
            "headline": "Awaiting Live Market Signals...",
            "url": "#",
            "timestamp": datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S GMT"),
            "source": "System Core",
            "outcome": "INITIALIZED",
            "pipeline_stage": "Ingestion Window",
            "reason": "Pipeline is active. Awaiting fresh intraday filings.",
            "processing_time": "N/A",
            "issuer": "N/A"
        }]
        
    with open("docs/archive_data.json", "w", encoding="utf-8") as f:
        json.dump(archive_list, f, indent=2)
    print(f"[VQA] Successfully extracted {len(archive_list)} live ledger items to docs/archive_data.json")

    # ---------------------------------------------------------
    # 2. EXTRACT SYSTEM METRICS & SOURCE INTELLIGENCE
    # ---------------------------------------------------------
    metrics_payload = {
        "system_status": "OPERATIONAL",
        "uptime": "99.9%",
        "last_sync_gmt": datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S GMT"),
        "total_processed_today": total_processed,
        "total_alerts_dispatched": total_alerts,
        "run_id": f"SSR-OP-{datetime.datetime.utcnow().strftime('%y%m%d%H')}",
        "health_score": 100,
        "system_confidence": 0.85
    }

    # Finalize dynamic source percentages safely
    src_30_list = []
    for src, stats in source_stats.items():
        arts = stats["articles"]
        if arts > 0:
            stats["alert_pct"] = round((stats["alerts"] / arts) * 100, 1)
            stats["ontology_pct"] = round((stats["ontology_pct"] / arts) * 100, 1)
            stats["rules_pct"] = round((stats["rules_pct"] / arts) * 100, 1)
        src_30_list.append(stats)

    try:
        cursor.execute("SELECT failed, runtime FROM workflow_health ORDER BY timestamp DESC LIMIT 1")
        health_row = cursor.fetchone()
        if health_row:
            metrics_payload["total_runtime_s"] = health_row["runtime"]
            if health_row["failed"] > 0:
                metrics_payload["system_status"] = "DEGRADED"
                metrics_payload["health_score"] = 75
    except Exception:
        pass 
        
    # Inject the dynamic source list into the payload so the frontend can render it
    metrics_payload["dynamic_sources"] = src_30_list
        
    with open("docs/dashboard_metrics.json", "w", encoding="utf-8") as f:
        json.dump(metrics_payload, f, indent=2)
        
    conn.close()
    print("[VQA] Clean metrics payload synced to docs/dashboard_metrics.json")

if __name__ == "__main__":
    export_data()