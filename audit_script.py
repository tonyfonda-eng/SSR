import json

try:
    with open('docs/archive_data.json', 'r') as f:
        archive_data = json.load(f)
        if isinstance(archive_data, dict) and 'ledger' in archive_data:
            archive_data = archive_data['ledger']
except FileNotFoundError:
    archive_data = []

stage_timings = {}
for a in archive_data:
    timings = a.get('performance_telemetry_ms', {})
    if isinstance(timings, str):
        try:
            timings = json.loads(timings)
        except:
            timings = {}
    for stage, t in timings.items():
        if stage not in stage_timings:
            stage_timings[stage] = []
        stage_timings[stage].append(t)

print("Average execution timings (ms) per stage:")
for stage, times in stage_timings.items():
    if not times: continue
    avg = sum(times) / len(times)
    print(f"  {stage}: {avg:.2f} ms (from {len(times)} samples)")
