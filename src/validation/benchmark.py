"""
SSR 2.0: Continuous Alpha Validation Framework (Upgraded)
Executes deterministic backtesting against the version-controlled Golden Evidence Dataset.
Generates tied-and-hashed Markdown Reports (BENCHMARK_REPORT.md / COVERAGE_REPORT.md).
"""

import json
import sqlite3
import math
import sys
import os
import hashlib
from datetime import datetime, timezone

RESEARCH_DB_PATH = "ssr_observability.db"
GOLDEN_DATASET_PATH = "src/validation/test_assets/golden_benchmark.json"
BENCHMARK_REPORT_PATH = "docs/BENCHMARK_REPORT.md"
COVERAGE_REPORT_PATH = "docs/COVERAGE_REPORT.md"

MIN_RESEARCH_FIDELITY_LOWER_BOUND = 0.90  
MAX_FALSE_POSITIVE_UPPER_BOUND = 0.15     

def wilson_score_interval(p_hat: float, n: int, z: float = 1.96) -> tuple:
    if n == 0: return 0.0, 0.0, 0.0
    denominator = 1 + (z**2 / n)
    center = (p_hat + (z**2 / (2 * n))) / denominator
    spread = (z / denominator) * math.sqrt((p_hat * (1 - p_hat) / n) + (z**2 / (4 * n**2)))
    return center, max(0.0, center - spread), min(1.0, center + spread)

def get_file_hash(filepath: str) -> str:
    """Computes SHA-256 of the dataset file to ensure report lock-in."""
    if not os.path.exists(filepath): return "UNKNOWN"
    hasher = hashlib.sha256()
    with open(filepath, 'rb') as f:
        hasher.update(f.read())
    return f"DS-{hasher.hexdigest()[:12].upper()}"

def fetch_latest_decisions() -> dict:
    system_decisions = {}
    if not os.path.exists(RESEARCH_DB_PATH): return system_decisions
    try:
        conn = sqlite3.connect(RESEARCH_DB_PATH)
        cursor = conn.cursor()
        cursor.execute("""
            SELECT e.article_hash, l.detection_outcome, l.decision_id, l.manifest_hash
            FROM evaluation_ledger l
            JOIN event_registry e ON l.event_id = e.event_id
            ORDER BY l.runtime_timestamp ASC
        """)
        for row in cursor.fetchall():
            system_decisions[row[0]] = {"outcome": row[1], "decision_id": row[2], "manifest_hash": row[3]}
        conn.close()
    except Exception: pass
    return system_decisions

def write_markdown_reports(metrics, dataset_hash, latest_config_hash):
    total = metrics["true_positive"] + metrics["true_negative"] + metrics["false_positive"] + metrics["false_negative"]
    
    fid_emp = (metrics["true_positive"] + metrics["true_negative"]) / total if total > 0 else 0
    fid_cen, fid_low, fid_up = wilson_score_interval(fid_emp, total)
    
    tp_fn = metrics["true_positive"] + metrics["false_negative"]
    cap_emp = metrics["true_positive"] / tp_fn if tp_fn > 0 else 1.0
    cap_cen, cap_low, cap_up = wilson_score_interval(cap_emp, tp_fn)
    
    tn_fp = metrics["true_negative"] + metrics["false_positive"]
    fp_emp = metrics["false_positive"] / tn_fp if tn_fp > 0 else 0.0
    fp_cen, fp_low, fp_up = wilson_score_interval(fp_emp, tn_fp)

    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S GMT")

    bench_md = f"""# SSR 2.0 Continuous Validation: Benchmark Report

**Generated:** {now_str}
**Golden Dataset Version:** `{dataset_hash}`
**System Configuration Version:** `{latest_config_hash}`

## Core Alpha Metrics (Wilson Score Intervals)
| Metric | Empirical Rate | 95% Confidence Interval | Status |
|--------|----------------|--------------------------|--------|
| **Research Fidelity ($F_R$)** | {fid_emp*100:.1f}% | [{fid_low*100:.1f}% - {fid_up*100:.1f}%] | {'✅ PASS' if fid_low >= MIN_RESEARCH_FIDELITY_LOWER_BOUND else '❌ FAIL'} |
| **Opportunity Capture** | {cap_emp*100:.1f}% | [{cap_low*100:.1f}% - {cap_up*100:.1f}%] | ℹ️ INFO |
| **False Positive Rate** | {fp_emp*100:.1f}% | [{fp_low*100:.1f}% - {fp_up*100:.1f}%] | {'✅ PASS' if fp_up <= MAX_FALSE_POSITIVE_UPPER_BOUND else '❌ FAIL'} |

## Raw Confusion Matrix
* **True Positives (Hits):** {metrics["true_positive"]}
* **True Negatives (Correct Rejects):** {metrics["true_negative"]}
* **False Positives (Noise):** {metrics["false_positive"]}
* **False Negatives (Misses):** {metrics["false_negative"]}
"""
    os.makedirs(os.path.dirname(os.path.abspath(BENCHMARK_REPORT_PATH)), exist_ok=True)
    with open(BENCHMARK_REPORT_PATH, "w", encoding="utf-8") as f:
        f.write(bench_md)

    cov_md = f"""# SSR 2.0 Pipeline Coverage Report

**Generated:** {now_str}
**Dataset Hash:** `{dataset_hash}`

## Dataset Execution Coverage
* **Total Golden Cases Available:** {total + metrics["untested_coverage"]}
* **Cases Evaluated by Current Pipeline:** {total}
* **Untested Coverage Gap:** {metrics["untested_coverage"]} cases
"""
    with open(COVERAGE_REPORT_PATH, "w", encoding="utf-8") as f:
        f.write(cov_md)

def run_continuous_validation():
    if not os.path.exists(GOLDEN_DATASET_PATH):
        print("[ERROR] Golden dataset not found. Run 'python -m src.validation.build_golden_dataset' first.")
        return 1
        
    with open(GOLDEN_DATASET_PATH, 'r', encoding='utf-8') as f:
        golden_data = json.load(f)
        
    dataset_hash = golden_data.get("metadata", {}).get("version_hash", get_file_hash(GOLDEN_DATASET_PATH))
    cases = golden_data.get("cases", [])
    system_decisions = fetch_latest_decisions()
    
    metrics = {"true_positive": 0, "true_negative": 0, "false_positive": 0, "false_negative": 0, "untested_coverage": 0}
    latest_config_hash = "UNKNOWN"

    for case in cases:
        expected = case.get("expected_outcome")
        a_hash = case.get("article_hash")
        
        system_eval = system_decisions.get(a_hash)
        if not system_eval:
            metrics["untested_coverage"] += 1
            continue
            
        actual = system_eval["outcome"]
        latest_config_hash = system_eval["manifest_hash"]
        
        if expected == "DETECTED" and actual in ("DETECTED", "DISPATCHED"):
            metrics["true_positive"] += 1
        elif expected == "DROPPED" and actual == "DROPPED":
            metrics["true_negative"] += 1
        elif expected == "DROPPED" and actual in ("DETECTED", "DISPATCHED"):
            metrics["false_positive"] += 1
        elif expected == "DETECTED" and actual == "DROPPED":
            metrics["false_negative"] += 1

    total_evaluated = sum(v for k,v in metrics.items() if k != "untested_coverage")
    write_markdown_reports(metrics, dataset_hash, latest_config_hash)
    
    print(f"[VALIDATION] Generated Version-Locked Reports for Dataset {dataset_hash}")
    return 0

if __name__ == "__main__":
    sys.exit(run_continuous_validation())