import re

with open('monitor.py', 'r') as f:
    content = f.read()

sig = "def _process_article(source_name, article_id, title, url, published, body, rules, playbook_map, global_exclusions=None, gold_standards=None, triage_all=False, funnel_metrics=None, issuer_memory=None, document_type=None, country=None, language=None, document_type_scores=None, ontology_stats=None, source_reliability_scores=None):"
new_sig = sig + """
    import time
    start_time = time.perf_counter()
    from src.monitoring import MetricsCollector
    metrics = MetricsCollector.get_instance()
    metrics.daily["downloaded"] += 1
    metrics.source_stats[source_name]["downloaded"] += 1
    
    def conclude(ret_val, stage, final_status, drop_reason, issuer_name="Unknown", event_family="Unknown"):
        elapsed_ms = (time.perf_counter() - start_time) * 1000
        metrics.log_article(article_id, source_name, url, title, country, language, document_type, issuer_name, event_family, stage, final_status, drop_reason, elapsed_ms)
        return ret_val
"""

content = content.replace(sig, new_sig)

# Deduplication silent skip
content = content.replace(
    "if article_exists(article_key):\n        return 0",
    "if article_exists(article_key):\n        return conclude(0, 'Database', 'Dropped', 'Duplicate Article')"
)

# Empty body
content = content.replace(
    "if funnel_metrics: funnel_metrics[3] += 1\n        return 0",
    "if funnel_metrics: funnel_metrics[3] += 1\n        return conclude(0, 'Download', 'Dropped', 'Empty Body')"
)

# AI Exhausted 1
content = content.replace(
    "if issuer == \"EXHAUSTED\":\n        print(\"    [CRITICAL] AI Providers are exhausted. Aborting ingestion loop to prevent spam and save cache.\")\n        return \"ABORT\"",
    "if issuer == \"EXHAUSTED\":\n        print(\"    [CRITICAL] AI Providers are exhausted. Aborting ingestion loop to prevent spam and save cache.\")\n        return conclude(\"ABORT\", 'Issuer Extraction', 'Dropped', 'AI Exhausted')"
)

# Issuer duplicate
content = content.replace(
    "return 1",
    "return conclude(1, 'Daily Memory', 'Dropped', 'Duplicate Issuer', issuer)",
    1
)

# Global exclusions
content = content.replace(
    "return 1",
    "return conclude(1, 'Global Exclusions', 'Dropped', 'Regex Failed', issuer)",
    1
)

# AI Exhausted 2
content = content.replace(
    "return \"ABORT\"",
    "return conclude(\"ABORT\", 'Rules Engine', 'Dropped', 'AI Exhausted', issuer)",
    1
)

# Private target
content = content.replace(
    "return 1",
    "return conclude(1, 'AI Classification', 'Dropped', 'Private Company', ticker)",
    1
)

# Exhausted 3
content = content.replace(
    "return \"ABORT\"",
    "return conclude(\"ABORT\", 'AI Classification', 'Dropped', 'AI Exhausted', ticker, event_family)",
    1
)

# False positive
content = content.replace(
    "return 1",
    "return conclude(1, 'AI Classification', 'Dropped', 'AI False Positive', ticker, event_family)",
    1
)

# Unknown event
content = content.replace(
    "return 1",
    "return conclude(1, 'AI Classification', 'Archived', 'Unknown Event', ticker, event_family)",
    1
)

# M&A Naked call failed options
content = content.replace(
    "return 1",
    "return conclude(1, 'AI Classification', 'Dropped', 'No Options Available', ticker, event_family)",
    1
)

# T12 Rejected
content = content.replace(
    "return 1",
    "return conclude(1, 'Playbook', 'Dropped', 'T12 Structural Floor Failed', ticker, event_family)",
    1
)

# Python update no material changes
content = content.replace(
    "return 1",
    "return conclude(1, 'Deduplication', 'Dropped', 'No Material Update', ticker, event_family)",
    1
)

# Final success (will replace the last return 1 at the end of the function)
content = content.replace(
    "    return 1\n",
    "    return conclude(1, 'Alert', 'Alert Sent', 'Email Dispatched', issuer, event_family)\n",
    1
)

with open('monitor.py', 'w') as f:
    f.write(content)
