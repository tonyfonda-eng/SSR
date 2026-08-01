import re
import sys
import shutil

# Make a backup
shutil.copy2('monitor.py', 'monitor.py.bak')

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
    
    ai_invoked = False
    
    def conclude(ret_val, pipeline_stage, outcome, reason, issuer_name="Unknown", event_family="Unknown"):
        elapsed_ms = (time.perf_counter() - start_time) * 1000
        metrics.log_article(article_id, source_name, url, title, country, language, document_type, issuer_name, event_family, pipeline_stage, outcome, reason, ai_invoked, elapsed_ms)
        return ret_val
"""

# If the old signature exists, replace it
if sig in content:
    content = content.replace(sig, new_sig)
else:
    # We might have the patched signature already, we need to rebuild it
    # We will just use regex to replace everything from def _process_article to `ai_invoked = False`
    pattern = re.compile(r'def _process_article\(.*?\):.*?def conclude\(.*?\):.*?return ret_val', re.DOTALL)
    content = pattern.sub(new_sig.strip() + "\n", content)
    # Actually, simpler to just start fresh if we already patched it...
    pass

# We will just do a fresh checkout of monitor.py from git and patch it again to avoid mess.
import subprocess
subprocess.run(["git", "checkout", "monitor.py"], check=True)

with open('monitor.py', 'r') as f:
    content = f.read()

content = content.replace(sig, new_sig)

# Deduplication silent skip
content = content.replace(
    "if article_exists(article_key):\n        return 0",
    "if article_exists(article_key):\n        return conclude(0, 'Database', 'Skipped', 'Duplicate Article')"
)

# Empty body
content = content.replace(
    "if funnel_metrics: funnel_metrics[3] += 1\n        return 0",
    "if funnel_metrics: funnel_metrics[3] += 1\n        return conclude(0, 'Download', 'Rejected', 'Empty Body')"
)

# AI Exhausted 1
content = content.replace(
    "if issuer == \"EXHAUSTED\":\n        print(\"    [CRITICAL] AI Providers are exhausted. Aborting ingestion loop to prevent spam and save cache.\")\n        return \"ABORT\"",
    "if issuer == \"EXHAUSTED\":\n        print(\"    [CRITICAL] AI Providers are exhausted. Aborting ingestion loop to prevent spam and save cache.\")\n        return conclude(\"ABORT\", 'Issuer Extraction', 'Aborted', 'AI Exhausted')"
)

# Issuer duplicate
content = content.replace(
    "return 1",
    "return conclude(1, 'Regex', 'Rejected', 'Duplicate Issuer', issuer)",
    1
)

# Global exclusions
content = content.replace(
    "return 1",
    "return conclude(1, 'Regex', 'Rejected', 'Global Exclusion', issuer)",
    1
)

# Set AI Invoked flag right before AI Extraction
content = content.replace(
    "ticker = extract_target_ticker(body)",
    "ai_invoked = True\n        ticker = extract_target_ticker(body)"
)

# AI Exhausted 2
content = content.replace(
    "return \"ABORT\"",
    "return conclude(\"ABORT\", 'Rules', 'Aborted', 'AI Exhausted', issuer)",
    1
)

# Private target
content = content.replace(
    "return 1",
    "return conclude(1, 'AI', 'Rejected', 'Private Company', ticker)",
    1
)

# Exhausted 3
content = content.replace(
    "return \"ABORT\"",
    "return conclude(\"ABORT\", 'AI', 'Aborted', 'AI Exhausted', ticker, event_family)",
    1
)

# False positive
content = content.replace(
    "return 1",
    "return conclude(1, 'AI', 'Rejected', 'False Positive', ticker, event_family)",
    1
)

# Unknown event
content = content.replace(
    "return 1",
    "return conclude(1, 'AI', 'Archived', 'Unknown Event', ticker, event_family)",
    1
)

# M&A Naked call failed options
content = content.replace(
    "return 1",
    "return conclude(1, 'Rules', 'Rejected', 'No Options Available', ticker, event_family)",
    1
)

# T12 Rejected
content = content.replace(
    "return 1",
    "return conclude(1, 'Playbook', 'Rejected', 'T12 Structural Floor Failed', ticker, event_family)",
    1
)

# Python update no material changes
content = content.replace(
    "return 1",
    "return conclude(1, 'Database', 'Rejected', 'No Material Update', ticker, event_family)",
    1
)

# Final success
content = content.replace(
    "    return 1\n",
    "    return conclude(1, 'Email', 'Alert Sent', 'Success', issuer, event_family)\n",
    1
)

with open('monitor.py', 'w') as f:
    f.write(content)
