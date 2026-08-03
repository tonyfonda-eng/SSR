"""
SSR 2.0: Concept Drift & Rules Intelligence Monitor
Analyzes the Immutable Evidence Repository to mathematically detect shifts
in corporate language (Ontology Z-Scores) and Rule efficacy.
"""

import sqlite3
import math
import datetime
import logging
from collections import defaultdict
from typing import List, Dict, Any

from src.monitoring import MetricsCollector

logger = logging.getLogger(__name__)
RESEARCH_DB_PATH = "ssr_observability.db"

def safe_div(n: float, d: float, default: float = 0.0) -> float:
    return n / d if d and d != 0 else default

def calculate_z_score(current_val: float, baseline_mean: float, baseline_std: float) -> float:
    if baseline_std == 0:
        return 0.0
    return (current_val - baseline_mean) / baseline_std

def get_date_windows() -> tuple:
    """Returns the boundaries for the 7-day current window and 90-day baseline window."""
    now = datetime.datetime.now(datetime.timezone.utc)
    current_start = now - datetime.timedelta(days=7)
    baseline_start = now - datetime.timedelta(days=90)
    
    return (
        now.strftime("%Y-%m-%d %H:%M:%S"),
        current_start.strftime("%Y-%m-%d %H:%M:%S"),
        baseline_start.strftime("%Y-%m-%d %H:%M:%S")
    )

def evaluate_ontology_drift() -> List[Dict[str, Any]]:
    """
    Computes rolling Z-Scores for ontology concept extraction frequencies.
    Detects if specific market terminology is surging or decaying.
    """
    now_str, current_start_str, baseline_start_str = get_date_windows()
    
    try:
        conn = sqlite3.connect(RESEARCH_DB_PATH)
        cursor = conn.cursor()
        
        # Pull all supporting ontology evidence over the last 90 days
        cursor.execute("""
            SELECT ae.assertion_key, el.runtime_timestamp, el.detection_outcome
            FROM atomic_evidence ae
            JOIN evaluation_ledger el ON ae.decision_id = el.decision_id
            WHERE ae.stage = 'Ontology' AND ae.evidence_direction = 'SUPPORTING'
              AND el.runtime_timestamp >= ?
        """, (baseline_start_str,))
        
        rows = cursor.fetchall()
        conn.close()
    except sqlite3.OperationalError as e:
        logger.warning(f"[DRIFT MONITOR] Ledger uninitialized or missing data: {e}")
        return []

    # Aggregate daily frequencies
    concept_daily_counts = defaultdict(lambda: defaultdict(int))
    concept_outcomes = defaultdict(lambda: {"alerts": 0, "total": 0})
    
    for assertion, ts_str, outcome in rows:
        # assertion_key looks like "Matched CONCEPT-092", we strip the prefix for cleaner display
        concept = assertion.replace("Matched Concept: ", "").replace("Matched ", "")
        
        # Extract YYYY-MM-DD
        day = ts_str.split(" ")[0]
        concept_daily_counts[concept][day] += 1
        
        concept_outcomes[concept]["total"] += 1
        if outcome in ("DETECTED", "DISPATCHED"):
            concept_outcomes[concept]["alerts"] += 1

    analytics = []
    
    for concept, daily_counts in concept_daily_counts.items():
        baseline_counts = []
        current_counts = []
        
        # Separate into windows
        for day_str, count in daily_counts.items():
            if day_str >= current_start_str.split(" ")[0]:
                current_counts.append(count)
            else:
                baseline_counts.append(count)
                
        # Fill missing days with 0s to ensure accurate means
        # (Simplified approximation for performance)
        baseline_mean = sum(baseline_counts) / max(83, len(baseline_counts)) if baseline_counts else 0.0
        current_mean = sum(current_counts) / 7.0
        
        # Calculate standard deviation for the baseline
        variance = sum((x - baseline_mean) ** 2 for x in baseline_counts) / max(83, len(baseline_counts)) if baseline_counts else 0.0
        baseline_std = math.sqrt(variance)
        
        z_score = calculate_z_score(current_mean, baseline_mean, baseline_std)
        
        # Conversion rate (How often does seeing this concept actually result in an alert?)
        conversion_rate = safe_div(concept_outcomes[concept]["alerts"], concept_outcomes[concept]["total"]) * 100.0
        
        if abs(z_score) >= 3.0:
            logger.info(f"[DRIFT ALARM] High vocabulary volatility detected for '{concept}'. Z-Score: {z_score:.2f}")

        analytics.append({
            "concept": concept,
            "frequency": concept_outcomes[concept]["total"],
            "z_score": round(z_score, 2),
            "alert_conversion": round(conversion_rate, 1)
        })

    # Sort by highest frequency
    return sorted(analytics, key=lambda x: x["frequency"], reverse=True)[:100]


def evaluate_rule_intelligence() -> List[Dict[str, Any]]:
    """
    Evaluates deterministic rule lineage to compute individual rule efficacy, 
    false positive contribution, and capture weighting.
    """
    now_str, current_start_str, baseline_start_str = get_date_windows()
    
    try:
        conn = sqlite3.connect(RESEARCH_DB_PATH)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT ae.source_component, ae.evidence_direction, ae.confidence_weight, el.detection_outcome
            FROM atomic_evidence ae
            JOIN evaluation_ledger el ON ae.decision_id = el.decision_id
            WHERE ae.stage = 'Rules' AND el.runtime_timestamp >= ?
        """, (baseline_start_str,))
        
        rows = cursor.fetchall()
        conn.close()
    except sqlite3.OperationalError:
        return []

    rule_stats = defaultdict(lambda: {"evaluated": 0, "supporting": 0, "opposing": 0, "alerts": 0, "weight_sum": 0.0})
    
    for component, direction, weight, outcome in rows:
        stats = rule_stats[component]
        stats["evaluated"] += 1
        
        if direction == "SUPPORTING":
            stats["supporting"] += 1
            stats["weight_sum"] += weight
            if outcome in ("DETECTED", "DISPATCHED"):
                stats["alerts"] += 1
        else:
            stats["opposing"] += 1

    analytics = []
    for rule, stats in rule_stats.items():
        avg_weight = safe_div(stats["weight_sum"], stats["supporting"])
        
        analytics.append({
            "rule": rule,
            "evaluated": stats["evaluated"],
            "supporting_hits": stats["supporting"],
            "alerts": stats["alerts"],
            "avg_weight": round(avg_weight, 2)
        })

    return sorted(analytics, key=lambda x: x["alerts"], reverse=True)


def check_pipeline_drift():
    """
    Main entrypoint invoked by the orchestrator at the end of the run.
    Calculates statistical drift and maps it to the MetricsCollector for dashboard rendering.
    """
    logger.info("[ANALYTICS] Running statistical Evidence DAG evaluation...")
    
    ontology_data = evaluate_ontology_drift()
    rule_data = evaluate_rule_intelligence()
    
    # Inject directly into the telemetry singleton for the HTML Manifest Generator to consume
    metrics = MetricsCollector.get_instance()
    metrics.daily["ontology_conversion"] = ontology_data
    metrics.daily["rule_analytics"] = rule_data
    
    logger.info(f"[ANALYTICS] Completed drift evaluation. Rules Evaluated: {len(rule_data)}, Concepts Evaluated: {len(ontology_data)}.")

if __name__ == "__main__":
    check_pipeline_drift()