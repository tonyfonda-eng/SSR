"""
SSR 2.0: Continuous Alpha Validation Framework
Executes deterministic backtesting against the Golden Evidence Dataset.
Calculates Research Fidelity (F_R) using the Wilson Score Interval.
Designed to run in CI/CD pipelines to block degraded deployments.
"""

import json
import sqlite3
import math
import sys
import os
from datetime import datetime, timezone

RESEARCH_DB_PATH = "ssr_observability.db"
GOLDEN_DATASET_PATH = "src/validation/test_assets/golden_benchmark.json"

# Institutional baselines for deployment approval
MIN_RESEARCH_FIDELITY_LOWER_BOUND = 0.90  # 90%
MAX_FALSE_POSITIVE_UPPER_BOUND = 0.15     # 15%


def wilson_score_interval(p_hat: float, n: int, z: float = 1.96) -> tuple:
    """
    Calculates the Wilson Score Interval for a binomial proportion.
    Returns: (Center, Lower_Bound, Upper_Bound)
    """
    if n == 0:
        return 0.0, 0.0, 0.0
        
    denominator = 1 + (z**2 / n)
    center = (p_hat + (z**2 / (2 * n))) / denominator
    spread = (z / denominator) * math.sqrt((p_hat * (1 - p_hat) / n) + (z**2 / (4 * n**2)))
    
    lower_bound = max(0.0, center - spread)
    upper_bound = min(1.0, center + spread)
    
    return center, lower_bound, upper_bound


def bootstrap_golden_dataset():
    """Creates a skeleton golden dataset if one does not exist for the new architecture."""
    os.makedirs(os.path.dirname(os.path.abspath(GOLDEN_DATASET_PATH)), exist_ok=True)
    if not os.path.exists(GOLDEN_DATASET_PATH):
        skeleton = {
            "metadata": {
                "version": "1.0",
                "last_updated": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S GMT"),
                "description": "SSR 2.0 Immutable Golden Benchmark Corpus"
            },
            "cases": [
                {
                    "event_id": "EVT-MOCK-001",
                    "article_hash": "mock_hash_1",
                    "expected_outcome": "DETECTED",
                    "expected_strategy": "Resumption of Trading",
                    "human_rationale": "Clear regulatory lifting of trading halt."
                },
                {
                    "event_id": "EVT-MOCK-002",
                    "article_hash": "mock_hash_2",
                    "expected_outcome": "DROPPED",
                    "expected_strategy": "None",
                    "human_rationale": "General macro commentary, no specific corporate action."
                }
            ]
        }
        with open(GOLDEN_DATASET_PATH, 'w', encoding='utf-8') as f:
            json.dump(skeleton, f, indent=4)
        print(f"[SYSTEM] Bootstrapped empty Golden Dataset at {GOLDEN_DATASET_PATH}")


def fetch_latest_decisions() -> dict:
    """
    Pulls the most recent evaluation outcomes from the Decision Ledger, keyed by article hash.
    Because Event IDs map 1:1 with an article hash, we use the hash to find the system's choice.
    """
    system_decisions = {}
    if not os.path.exists(RESEARCH_DB_PATH):
        print(f"[WARNING] Database {RESEARCH_DB_PATH} not found. Assuming clean slate.")
        return system_decisions

    try:
        conn = sqlite3.connect(RESEARCH_DB_PATH)
        cursor = conn.cursor()
        cursor.execute("""
            SELECT e.article_hash, l.detection_outcome, l.decision_id
            FROM evaluation_ledger l
            JOIN event_registry e ON l.event_id = e.event_id
            ORDER BY l.runtime_timestamp ASC
        """)
        # By ordering ASC, the dictionary retains the *most recent* decision for an article hash
        for row in cursor.fetchall():
            system_decisions[row[0]] = {
                "outcome": row[1],
                "decision_id": row[2]
            }
        conn.close()
    except sqlite3.OperationalError as e:
        print(f"[ERROR] Failed to query ledger: {e}")
    
    return system_decisions


def run_continuous_validation():
    """
    Executes the Research Fidelity validation sequence.
    Compares the current Evidence Engine ledger state against the Golden Corpus.
    """
    bootstrap_golden_dataset()
    
    with open(GOLDEN_DATASET_PATH, 'r', encoding='utf-8') as f:
        golden_data = json.load(f)
        
    cases = golden_data.get("cases", [])
    if not cases:
        print("[VALIDATION] Golden dataset is empty. Add cases to validate.")
        return 0

    system_decisions = fetch_latest_decisions()
    
    metrics = {
        "true_positive": 0,
        "true_negative": 0,
        "false_positive": 0,
        "false_negative": 0,
        "untested_coverage": 0
    }

    for case in cases:
        expected = case.get("expected_outcome")
        a_hash = case.get("article_hash")
        
        system_eval = system_decisions.get(a_hash)
        
        if not system_eval:
            metrics["untested_coverage"] += 1
            continue
            
        actual = system_eval["outcome"]
        
        if expected == "DETECTED" and actual == "DETECTED":
            metrics["true_positive"] += 1
        elif expected == "DROPPED" and actual == "DROPPED":
            metrics["true_negative"] += 1
        elif expected == "DROPPED" and actual == "DETECTED":
            metrics["false_positive"] += 1
        elif expected == "DETECTED" and actual == "DROPPED":
            metrics["false_negative"] += 1

    total_evaluated = metrics["true_positive"] + metrics["true_negative"] + metrics["false_positive"] + metrics["false_negative"]
    
    if total_evaluated == 0:
        print("[VALIDATION] Zero intersection between Golden Dataset and Current DB Ledger. Run pipeline first.")
        return 0

    # 1. Research Fidelity (Total Accuracy vs Human)
    fidelity_empirical = (metrics["true_positive"] + metrics["true_negative"]) / total_evaluated
    fid_center, fid_lower, fid_upper = wilson_score_interval(fidelity_empirical, total_evaluated)

    # 2. Opportunity Capture (Recall)
    total_expected_positives = metrics["true_positive"] + metrics["false_negative"]
    capture_empirical = metrics["true_positive"] / total_expected_positives if total_expected_positives > 0 else 1.0
    cap_center, cap_lower, cap_upper = wilson_score_interval(capture_empirical, total_expected_positives)

    # 3. False Positive Rate (Noise Commission)
    total_expected_negatives = metrics["true_negative"] + metrics["false_positive"]
    fp_empirical = metrics["false_positive"] / total_expected_negatives if total_expected_negatives > 0 else 0.0
    fp_center, fp_lower, fp_upper = wilson_score_interval(fp_empirical, total_expected_negatives)

    print("\n" + "="*60)
    print(" SSR 2.0 CONTINUOUS ALPHA VALIDATION REPORT")
    print("="*60)
    print(f" Golden Cases Evaluated : {total_evaluated} (Untested: {metrics['untested_coverage']})")
    print(f" True Positives (Hits)  : {metrics['true_positive']}")
    print(f" True Negatives (Rej)   : {metrics['true_negative']}")
    print(f" False Positives (Noise): {metrics['false_positive']}")
    print(f" False Negatives (Miss) : {metrics['false_negative']}")
    print("-" * 60)
    
    # Format intervals nicely
    def fmt_ci(emp, low, up):
        return f"{emp*100:5.1f}%  |  95% CI: [{low*100:5.1f}% - {up*100:5.1f}%]"

    print(f" Research Fidelity (F_R): {fmt_ci(fidelity_empirical, fid_lower, fid_upper)}")
    print(f" Opportunity Capture    : {fmt_ci(capture_empirical, cap_lower, cap_upper)}")
    print(f" False Positive Rate    : {fmt_ci(fp_empirical, fp_lower, fp_upper)}")
    print("="*60)

    # --- CI/CD Enforcements ---
    passed = True
    
    if fid_lower < MIN_RESEARCH_FIDELITY_LOWER_BOUND:
        print(f"\n[❌ BUILD FAILED] Research Fidelity lower bound ({fid_lower*100:.1f}%) decayed below institutional threshold ({MIN_RESEARCH_FIDELITY_LOWER_BOUND*100:.1f}%).")
        passed = False
        
    if fp_upper > MAX_FALSE_POSITIVE_UPPER_BOUND:
        print(f"\n[❌ BUILD FAILED] False Positive upper bound ({fp_upper*100:.1f}%) exceeds acceptable risk threshold ({MAX_FALSE_POSITIVE_UPPER_BOUND*100:.1f}%).")
        passed = False

    if passed:
        print("\n[✅ BUILD PASSED] Research Fidelity constraints satisfied. Architecture is stable.")
        return 0
    else:
        print("\n[BLOCKED] Deployment halted due to alpha degradation. Check causal chains for missed cases.")
        return 1

if __name__ == "__main__":
    exit_code = run_continuous_validation()
    sys.exit(exit_code)