import json
import os
import datetime
from src.audit.queries import (
    get_source_coverage,
    get_historical_source_averages,
    get_audit_source_metrics,
    get_lifetime_source_reliability
)
from src.audit.daily_audit import (
    calculate_anomaly,
    get_traffic_light,
    get_scraper_grade
)

def export_realtime_audit(filepath="docs/realtime_audit.json"):
    today_str = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d")
    
    source_coverage = get_source_coverage(today_str)
    hist_30d = get_historical_source_averages(today_str, days=30)
    audit_sources = get_audit_source_metrics(today_str)
    lifetime_rel = get_lifetime_source_reliability()
    
    audit_source_map = {s['source']: s for s in audit_sources}
    
    realtime_data = []
    
    for s in source_coverage:
        name = s['source']
        raw = s['total_articles']
        avg = hist_30d.get(name, 0)
        dev_pct = calculate_anomaly(raw, avg)
        
        audit_meta = audit_source_map.get(name, {})
        emergency_stop = bool(audit_meta.get('emergency_stop'))
        reason = str(audit_meta.get('reasons', '') or '')
        
        # Capture TRUE raw volume from the ingestion ledger
        raw = audit_meta.get('total_raw', 0)
        # Capture unique volume that passed deduplication
        unique = audit_meta.get('total_unique', 0)
        
        # If the source hasn't run yet today, fallback to the screening log count
        if raw == 0 and s['total_articles'] > 0:
            raw = s['total_articles']
            unique = s['unique_articles']
            
        avg = hist_30d.get(name, 0)
        dev_pct = calculate_anomaly(raw, avg)
        
        grade = get_scraper_grade(dev_pct, emergency_stop)
        light = get_traffic_light(dev_pct) if not emergency_stop else "🔴"
        
        realtime_data.append({
            "source": name,
            "mode": s['ingestion_mode'],
            "grade": grade,
            "status_light": light,
            "raw": raw,
            "unique": unique,
            "avg_30d": round(avg, 1),
            "dev_pct": round(dev_pct, 1),
            "lifetime_rel": round(lifetime_rel.get(name, 100.0), 1),
            "emergency_stop": emergency_stop,
            "reason": reason
        })
        
    os.makedirs(os.path.dirname(os.path.abspath(filepath)), exist_ok=True)
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump({"timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(), "source_metrics": realtime_data}, f, indent=2)
        
    print(f"[EXPORT] Successfully wrote realtime audit to {filepath}")
    return True

if __name__ == "__main__":
    export_realtime_audit()
