import json
from collections import Counter
with open("audit_data.json") as f:
    d = json.load(f)

print("=== Q1 FUNNEL ===")
funnel = d["funnel_agg"]
stages = ["dedupe_hash", "dedupe_issuer_memory", "exclude_global_keywords", "exclude_issuer_feed", "ontology_concepts", "regex_rules", "python_issuer_extraction", "python_ticker_lookup", "ai_ticker_resolution", "entity_confidence", "tradeability_check", "liquidity_check", "financial_market_cap", "financial_t12_floor", "options_chain_check", "playbook_gate", "ai_event_classification", "ai_confidence", "alert_generation", "email_sent"]
for s in stages:
    data = funnel.get(s, {"entered":0, "passed":0, "rejected":0})
    entered = data.get("entered", 0)
    passed = data.get("passed", 0)
    rejected = data.get("rejected", 0)
    pct = round(passed / entered * 100, 2) if entered > 0 else 0
    print(f"{s} | {entered} | {passed} | {rejected} | {pct}%")

print("\n=== Q12 DROP REASONS ===")
for r in d.get("q12_drop_reasons", []):
    print(r)

print("\n=== Q8 ONTO SCORES ===")
scores = d.get("onto_scores", [])
print("Total scores:", len(scores))
print("Score exactly 0.0:", scores.count(0.0))

print("\n=== Q14 PLAYBOOKS ===")
print(d.get("q14_playbooks"))

