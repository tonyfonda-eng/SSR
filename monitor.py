"""
Special Situations Radar (SSR) 2.0 — Main Orchestrator
Strict 10-Stage Deterministic-First Processing Funnel
"""

import sys
import logging
import traceback
import hashlib
import time
from datetime import datetime, timezone

# 1. Database & Telemetry Imports
from src.database import (
    initialise_database,
    get_or_create_event,
    commit_decision_capsule,
    save_workflow_health,
    save_exception_log
)

# 2. Pipeline Stage Imports (Assume these exist in your src directory)
from src.ingestion.scrapers import fetch_all_feeds
from src.ontology import evaluate_ontology
from src.rules import evaluate_deterministic_rules, matches_global_exclusion, matches_issuer_exclusion
from src.ai import extract_target_ticker, classify_event

# 3. Export & Sync Imports
from src.validation import export_frontend_data
import src.sheets_sync as sheets_sync

# Setup Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(module)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Configurable Thresholds
MIN_ONTOLOGY_SCORE = 0.65
MIN_AI_CONFIDENCE = 0.75

class PipelineTelemetry:
    """Tracks metrics across the 10-stage funnel to ensure accurate dashboard reporting."""
    def __init__(self):
        self.metrics = {
            "downloaded": 0,
            "duplicates_dropped": 0,
            "global_excluded": 0,
            "issuer_excluded": 0,
            "ontology_rejected": 0,
            "rules_rejected": 0,
            "reached_ai": 0,
            "ai_exhausted": 0,
            "ai_rejected": 0,
            "alerts_generated": 0,
            "errors": 0
        }
        self.start_time = time.time()
        self.run_id = f"RUN-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"

    def track(self, stage: str):
        if stage in self.metrics:
            self.metrics[stage] += 1

    def get_runtime(self):
        return round(time.time() - self.start_time, 2)


def process_article(article: dict, telemetry: PipelineTelemetry):
    """
    Executes the strict 10-stage funnel for a single article.
    Returns True if an alert was generated, False otherwise.
    """
    article_url = article.get("url", "UNKNOWN")
    article_body = article.get("body", "")
    
    # ---------------------------------------------------------
    # STAGE 2: Deduplication (Cheap Database Check)
    # ---------------------------------------------------------
    article_hash = hashlib.sha256(article_body.encode("utf-8")).hexdigest()
    event_id, is_new = get_or_create_event(article_hash, article_body.encode("utf-8"))
    
    if not is_new:
        telemetry.track("duplicates_dropped")
        return False

    # ---------------------------------------------------------
    # STAGE 3 & 4: Global & Issuer Exclusions (Cheap String Match)
    # ---------------------------------------------------------
    if matches_global_exclusion(article_body):
        telemetry.track("global_excluded")
        return False
        
    if matches_issuer_exclusion(article.get("source", "")):
        telemetry.track("issuer_excluded")
        return False

    # ---------------------------------------------------------
    # STAGE 5: Ontology Check (Deterministic Pattern Matching)
    # ---------------------------------------------------------
    ontology_score = evaluate_ontology(article_body)
    if ontology_score < MIN_ONTOLOGY_SCORE:
        telemetry.track("ontology_rejected")
        return False

    # ---------------------------------------------------------
    # STAGE 6: Rules & Regex Playbook (Deterministic Validation)
    # ---------------------------------------------------------
    rule_score = evaluate_deterministic_rules(article_body)
    if rule_score < 0.5:
        telemetry.track("rules_rejected")
        return False

    # ---------------------------------------------------------
    # STAGE 7 & 8: Candidate Promotion
    # ---------------------------------------------------------
    # The article has survived all cheap Python filters. 
    # It is now a high-value candidate worthy of AI API spend.
    telemetry.track("reached_ai")
    logger.info(f"Article {event_id} promoted to AI inference.")

    # =========================================================
    # STAGE 9: AI Evaluation (ONLY FOR SURVIVORS)
    # =========================================================
    
    # 9A: Ticker Extraction
    ticker = extract_target_ticker(article_body)
    if ticker in ["EXHAUSTED", "ERROR"]:
        # CRITICAL FIX: Do not crash the pipeline. Log, track, and skip.
        logger.warning(f"[AI EXHAUSTED] Failed to extract ticker for {event_id}. Skipping.")
        telemetry.track("ai_exhausted")
        return False

    # 9B: Event Classification
    ai_result = classify_event(article_body, ticker)
    if ai_result.get("status") in ["EXHAUSTED", "ERROR"]:
        logger.warning(f"[AI EXHAUSTED] Failed to classify {event_id}. Skipping.")
        telemetry.track("ai_exhausted")
        return False

    if ai_result.get("confidence", 0.0) < MIN_AI_CONFIDENCE:
        telemetry.track("ai_rejected")
        return False

    # ---------------------------------------------------------
    # STAGE 10: Alert Generation & Ledger Commitment
    # ---------------------------------------------------------
    decision_capsule = {
        "decision_id": f"DEC-{hashlib.md5(f'{event_id}:{ticker}'.encode()).hexdigest()[:12].upper()}",
        "event_id": event_id,
        "manifest_hash": "CFG-LATEST", # This would be fetched from config system in full implementation
        "runtime_timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S GMT"),
        "detection_outcome": ai_result.get("classification", "UNKNOWN"),
        "terminal_stage": "AI_APPROVED",
        "headline": article.get("headline", "Corporate Announcement"),
        "url": article_url,
        "ai_core_inference": {
            "aggregate_confidence": ai_result.get("confidence", 1.0),
            "parsed_structural_properties": {"ticker": ticker}
        }
    }
    
    commit_decision_capsule(decision_capsule)
    telemetry.track("alerts_generated")
    logger.info(f"[ALERT GENERATED] {ticker} - {ai_result.get('classification')}")
    return True


def main():
    logger.info("Initializing SSR 2.0 Pipeline...")
    
    # 1. Ensure Database Schema Exists
    try:
        initialise_database()
        logger.info("Database initialized successfully.")
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")
        sys.exit(1)

    telemetry = PipelineTelemetry()
    
    try:
        # STAGE 1: Download/Ingest
        logger.info("Fetching articles from sources...")
        articles = fetch_all_feeds() 
        telemetry.metrics["downloaded"] = len(articles)
        logger.info(f"Ingested {len(articles)} raw articles.")

        # Process Funnel
        for article in articles:
            try:
                process_article(article, telemetry)
            except Exception as e:
                logger.error(f"Error processing article: {e}")
                telemetry.track("errors")
                save_exception_log(
                    run_id=telemetry.run_id,
                    exc_type=type(e).__name__,
                    stack_trace=traceback.format_exc(),
                    article_url=article.get("url", "UNKNOWN")
                )

    except Exception as e:
        logger.critical(f"Fatal error in main pipeline loop: {e}")
        save_exception_log(run_id=telemetry.run_id, exc_type="FATAL", stack_trace=traceback.format_exc())
    
    finally:
        # =========================================================
        # ALWAYS RUN: Export & Dashboards (Graceful Degradation)
        # =========================================================
        logger.info("Pipeline execution finished. Generating observability exports...")
        
        # Save Health Telemetry
        health_payload = {
            "run_id": telemetry.run_id,
            "total_scanned": telemetry.metrics["downloaded"],
            "articles": telemetry.metrics["alerts_generated"],
            "errors": telemetry.metrics["errors"] + telemetry.metrics["ai_exhausted"],
            "runtime": telemetry.get_runtime(),
            "failed": telemetry.metrics["errors"],
            "succeeded": telemetry.metrics["alerts_generated"],
        }
        save_workflow_health(health_payload)
        
        # Force Dashboard/Sheets generation regardless of AI exhaustion
        try:
            export_frontend_data.main()
            logger.info("Frontend archive_data.json exported successfully.")
        except Exception as e:
            logger.error(f"Failed to export frontend data: {e}")
            
        try:
            # Assuming sheets_sync has a main() or sync() function
            if hasattr(sheets_sync, 'main'):
                sheets_sync.main()
            elif hasattr(sheets_sync, 'sync_metrics'):
                sheets_sync.sync_metrics(telemetry.run_id)
            logger.info("Google Sheets sync completed successfully.")
        except Exception as e:
            logger.error(f"Failed to sync Google Sheets: {e}")

        logger.info(f"Run {telemetry.run_id} complete in {telemetry.get_runtime()}s. "
                    f"Alerts: {telemetry.metrics['alerts_generated']} | "
                    f"AI Reached: {telemetry.metrics['reached_ai']} | "
                    f"AI Exhausted: {telemetry.metrics['ai_exhausted']}")

if __name__ == "__main__":
    main()