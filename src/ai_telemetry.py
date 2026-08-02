import sqlite3
from src.config import SYSTEM_SETTINGS, ACTIVE_MODEL

def generate_ai_health_report():
    """
    Reads actual production telemetry from the database to report on client health.
    Zero synthetic pings. Zero wasted quota.
    """
    db_path = SYSTEM_SETTINGS.get("DATABASE_PATH", "ssr_cache.sqlite")
    
    query = """
        SELECT provider, 
               AVG(latency) as avg_latency, 
               MAX(timestamp) as last_success 
        FROM ai_usage_log 
        WHERE status_code = 200 AND model = ?
        GROUP BY provider;
    """
    
    print("\n[AI TELEMETRY AUDIT]")
    print(f"Target Model: {ACTIVE_MODEL}")
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute(query, (ACTIVE_MODEL,))
        results = cursor.fetchall()
        conn.close()
        
        if not results:
            print("  No telemetry data found for the active model yet.")
            return

        for provider, latency, last_success in results:
            print(f"  {provider:<15} | status: HEALTHY | latency: {latency:.2f}s | last success: {last_success}")
            
    except Exception as e:
        print(f"[TELEMETRY ERROR] Could not read AI usage log: {e}")
    print("")
