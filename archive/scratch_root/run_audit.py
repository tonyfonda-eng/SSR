import sqlite3
import json
import random
from collections import defaultdict

res = {}

# --- DB Connections ---
try:
    dev_conn = sqlite3.connect("ssr_devops.db")
    dev_conn.row_factory = sqlite3.Row
    res_conn = sqlite3.connect("ssr_observability.db")
    res_conn.row_factory = sqlite3.Row
except Exception as e:
    print(f"Error connecting to DBs: {e}")
    exit(1)

# --- SECTION 1 ---
last_20 = list(dev_conn.execute("SELECT * FROM workflow_health ORDER BY timestamp DESC LIMIT 20"))
agg = defaultdict(lambda: {"entered": 0, "passed": 0, "rejected": 0})
run_ids = []
for r in last_20:
    run_ids.append(r["run_id"])
    if r["funnel_telemetry"]:
        try:
            funnel = json.loads(r["funnel_telemetry"])
            for stage, data in funnel.items():
                agg[stage]["entered"] += data.get("entered", 0)
                agg[stage]["passed"] += data.get("passed", 0)
                agg[stage]["rejected"] += data.get("rejected", 0)
        except:
            pass

res["funnel_agg"] = dict(agg)
res["num_runs"] = len(last_20)

# --- SECTION 2 ---
q3 = {"reached_send_alert": agg.get("alert_generation", {}).get("entered", 0)}
res["q3"] = q3

# --- SECTION 3 ---
# Q6: List 100 highest scoring rejected articles
q6_query = """
    SELECT 
        f.headline, f.source_url as url, e.terminal_stage as final_stage, 
        e.detection_outcome, e.evidence_completeness_score, e.ontology_metadata, e.market_data_snapshot
    FROM evaluation_ledger e
    LEFT JOIN factual_metadata f ON e.decision_id = f.decision_id
    WHERE e.detection_outcome != 'PASS'
    AND e.terminal_stage != 'dedupe_hash'
    LIMIT 100
"""
# Better to get actual drop reasons from article_screening_log, but let's just get article_screening_log where outcome != PASS
q6_alt = """
    SELECT headline, source, ticker, final_stage, drop_reason
    FROM article_screening_log
    WHERE outcome != 'PASS' AND final_stage NOT IN ('dedupe_hash', 'ontology_concepts')
    ORDER BY timestamp DESC
    LIMIT 100
"""
rejected_samples = [dict(row) for row in res_conn.execute(q6_alt)]
res["q6_rejected"] = rejected_samples

# --- SECTION 4 ---
q8_query = "SELECT ontology_metadata FROM evaluation_ledger ORDER BY runtime_timestamp DESC LIMIT 5000"
onto_scores = []
zero_fails = []
for row in res_conn.execute(q8_query):
    if row["ontology_metadata"]:
        try:
            m = json.loads(row["ontology_metadata"])
            s = m.get("score", 0.0)
            onto_scores.append(s)
            if s == 0.0 and len(zero_fails) < 100:
                zero_fails.append(m)
        except:
            pass

res["onto_scores"] = onto_scores
res["onto_failures"] = random.sample(zero_fails, min(20, len(zero_fails))) if zero_fails else []

# --- SECTION 6 ---
q12_reasons = list(res_conn.execute("""
    SELECT drop_reason, count(*) as c 
    FROM article_screening_log 
    WHERE outcome != 'PASS'
    GROUP BY drop_reason
"""))
res["q12_drop_reasons"] = [dict(r) for r in q12_reasons]

# Financial T12
q13_query = """
    SELECT ticker, drop_reason, final_stage
    FROM article_screening_log
    WHERE final_stage = 'financial_t12_floor'
    LIMIT 100
"""
t12_fails = [dict(row) for row in res_conn.execute(q13_query)]
res["q13_t12_fails"] = t12_fails

# --- SECTION 7 ---
q14_query = "SELECT event_family, count(*) as c FROM article_screening_log WHERE outcome = 'PASS' GROUP BY event_family"
q14_results = [dict(row) for row in res_conn.execute(q14_query)]
res["q14_playbooks"] = q14_results

with open("audit_data.json", "w") as f:
    json.dump(res, f)
print("done")
