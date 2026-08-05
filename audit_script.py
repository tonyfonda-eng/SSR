import json
import time

try:
    with open('docs/screening_log.json', 'r') as f:
        screening_data = json.load(f)
        if isinstance(screening_data, dict) and 'screening_log' in screening_data:
            screening_data = screening_data['screening_log']
except FileNotFoundError:
    screening_data = []

try:
    with open('docs/archive_data.json', 'r') as f:
        archive_data = json.load(f)
        if isinstance(archive_data, dict) and 'ledger' in archive_data:
            archive_data = archive_data['ledger']
except FileNotFoundError:
    archive_data = []

# Group by run_id
runs = {}
for s in screening_data:
    r_id = s.get('run_id')
    if r_id:
        if r_id not in runs:
            runs[r_id] = []
        runs[r_id].append(s)

# Analyze last run
run_ids = sorted(list(runs.keys()))
last_run_id = run_ids[-1] if run_ids else None
last_run = runs.get(last_run_id, [])

print(f"Total runs tracked in screening log: {len(run_ids)}")
if last_run_id:
    print(f"Stats for last run ({last_run_id}):")
    print(f"Total articles screened: {len(last_run)}")
    
    ontology_rejects = [a for a in last_run if a.get('final_stage') == 'ontology_concepts' and a.get('outcome') == 'DROPPED']
    print(f"Ontology rejects in last run: {len(ontology_rejects)}")
    
    ai_reached = [a for a in last_run if a.get('final_stage') in ('ai_ticker_resolution', 'ai_event_classification', 'ai_confidence_gate', 'AI_APPROVED')]
    print(f"Articles reaching AI in last run: {len(ai_reached)}")
    
    dupes = [a for a in last_run if a.get('drop_reason') == 'dropped_hash_duplicate']
    print(f"Duplicates removed in last run: {len(dupes)}")

# Duplicates removed in last 30 runs
last_30_runs = run_ids[-30:]
dupes_30 = 0
for r_id in last_30_runs:
    dupes_30 += len([a for a in runs[r_id] if a.get('drop_reason') == 'dropped_hash_duplicate'])
print(f"Duplicates removed in last {len(last_30_runs)} runs: {dupes_30}")

# Articles reaching AI in last 100 runs
last_100_runs = run_ids[-100:]
ai_100 = 0
for r_id in last_100_runs:
    ai_100 += len([a for a in runs[r_id] if a.get('final_stage') in ('ai_ticker_resolution', 'ai_event_classification', 'ai_confidence_gate', 'AI_APPROVED')])
print(f"Articles reached AI in last {len(last_100_runs)} runs: {ai_100}")

# Performance / Exec timings (from archive_data.json)
stage_timings = {}
for a in archive_data:
    timings = a.get('execution_timings', {})
    for stage, t in timings.items():
        if stage not in stage_timings:
            stage_timings[stage] = []
        stage_timings[stage].append(t)

print("Average execution timings (ms) per stage:")
for stage, times in stage_timings.items():
    avg = sum(times) / len(times)
    print(f"  {stage}: {avg:.2f} ms (from {len(times)} samples)")
    
