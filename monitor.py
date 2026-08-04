"""
Special Situations Radar (SSR) 2.0 — Main Orchestrator
Strict 10-Stage Deterministic-First Processing Funnel
"""

import sys
import logging
import traceback
import hashlib
import time
import json
from datetime import datetime, timezone

# 1. Database & Telemetry Imports
from src.database import (
    initialise_database,
    get_or_create_event,
    commit_decision_capsule,
    save_workflow_health,
    save_exception_log,
    save_config_snapshot
)

# 2. Pipeline Stage Imports
from src.ingestion.scrapers import fetch_all_feeds
from src.ontology import evaluate_ontology
from src.ontology.engine import load_ontology
from src.rules import matches_global_exclusion, matches_issuer_exclusion
from src.rules_engine import evaluate as evaluate_deterministic_rules
from src.ai import extract_target_ticker, classify_event

# 3. Export & Sync Imports
from src.validation import export_frontend_data
import src.sheets_sync as sheets_sync

# 4. Configuration & "Brain" Imports
from src.config.settings import SHEET_URL
from src.sheets import (
    load_rules, load_global_exclusions, load_document_type_scores,
    load_semantic_concepts, load_event_statuses, get_system_settings,
    load_playbooks, load_sources
)

# Setup Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(module)s - %(message)s"
)
logger = logging.getLogger(__name__)

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


def process_article(article: dict, telemetry: PipelineTelemetry, config_manifest: dict, manifest_hash: str):
    """
    Executes the strict 10-stage funnel for a single article, completely driven 
    by the dynamically injected config_manifest (The Brain).
    """
    article_url = article.get("url", "UNKNOWN")
    article_body = article.get("body", "")
    
    # Extract dynamic thresholds from the settings sheet (fallback to safe defaults)
    settings = config_manifest.get("settings", [])
    sys_settings = settings[0] if settings else {}
    min_ontology_score = float(sys_settings.get("MIN_ONTOLOGY_SCORE", 0.65))
    min_ai_confidence = float(sys_settings.get("MIN_AI_CONFIDENCE", 0.75))
    rule_threshold = int(sys_settings.get("RULE_THRESHOLD", 10))
    
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
    if matches_global_exclusion(article_body, config_manifest.get("global_exclusions", [])):
        telemetry.track("global_excluded")
        return False
        
    if matches_issuer_exclusion(article.get("source", ""), config_manifest.get("sources", [])):
        telemetry.track("issuer_excluded")
        return False

    # ---------------------------------------------------------
    # STAGE 5: Ontology Check (Deterministic Pattern Matching)
    # ---------------------------------------------------------
    ontology_score = evaluate_ontology(article_body, config_manifest.get("semantic_concepts", []))
    if ontology_score < min_ontology_score:
        telemetry.track("ontology_rejected")
        return False

    # ---------------------------------------------------------
    # STAGE 6: Rules & Regex Playbook (Deterministic Validation)
    # ---------------------------------------------------------
    # Dynamically evaluate the text against the latest version-locked rule packs
    rule_results = evaluate_deterministic_rules(
        article={"raw_text": article_body, "document_type": article.get("document_type", "Unknown")},
        rules=config_manifest.get("rules", []),
        document_type_scores=config_manifest.get("document_type_scores", []),
        ontology_concepts=[(c.get("Concept ID"), c.get("Weight", 1.0)) for c in config_manifest.get("semantic_concepts", []) if str(c.get("Active", "TRUE")).upper() == "TRUE"],
        ontology_statuses=config_manifest.get("event_statuses", []),
        threshold=rule_threshold
    )
    
    if not rule_results:
        telemetry.track("rules_rejected")
        return False

    # ---------------------------------------------------------
    # STAGE 7 & 8: Candidate Promotion
    # ---------------------------------------------------------
    # The article has survived all dynamic Python filters dictated by the worksheet.
    telemetry.track("reached_ai")
    logger.info(f"Article {event_id} promoted to AI inference.")

    # =========================================================
    # STAGE 9: AI Evaluation (ONLY FOR SURVIVORS)
    # =========================================================
    
    # 9A: Ticker Extraction
    ticker = extract_target_ticker(article_body)
    if ticker in ["EXHAUSTED", "ERROR"]:
        logger.warning(f"[AI EXHAUSTED] Failed to extract ticker for {event_id}. Skipping.")
        telemetry.track("ai_exhausted")
        return False

    # 9B: Event Classification
    ai_result = classify_event(article_body, ticker)
    if ai_result.get("status") in ["EXHAUSTED", "ERROR"]:
        logger.warning(f"[AI EXHAUSTED] Failed to classify {event_id}. Skipping.")
        telemetry.track("ai_exhausted")
        return False

    if ai_result.get("confidence", 0.0) < min_ai_confidence:
        telemetry.track("ai_rejected")
        return False

    # ---------------------------------------------------------
    # STAGE 10: Alert Generation & Ledger Commitment
    # ---------------------------------------------------------
    decision_capsule = {
        "decision_id": f"DEC-{hashlib.md5(f'{event_id}:{ticker}'.encode()).hexdigest()[:12].upper()}",
        "event_id": event_id,
        "manifest_hash": manifest_hash,
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
    
    # =========================================================
    # THE BRAIN: Sync and Lock Configuration Manifest
    # =========================================================
    try:
        logger.info("Syncing Configuration Manifest from Google Sheets (The Brain)...")
        
        # Bootstrap global Ontology Taxonomy mappings
        load_ontology(SHEET_URL)
        
        # Load all dynamic tables
        config_manifest = {
            "rules": load_rules(SHEET_URL),
            "global_exclusions": load_global_exclusions(SHEET_URL),
            "sources": load_sources(SHEET_URL),
            "document_type_scores": load_document_type_scores(SHEET_URL),
            "semantic_concepts": load_semantic_concepts(SHEET_URL),
            "event_statuses": load_event_statuses(SHEET_URL),
            "settings": get_system_settings(SHEET_URL),
            "playbooks": load_playbooks(SHEET_URL)
        }
        
        # Compute exact SHA-256 signature and lock it into the database for the run
        config_json = json.dumps(config_manifest, sort_keys=True)
        manifest_hash = f"CFG-{hashlib.sha256(config_json.encode('utf-8')).hexdigest()[:12].upper()}"
        save_config_snapshot(manifest_hash, telemetry.run_id, config_json)
        
        logger.info(f"Locked Immutable Configuration Manifest: {manifest_hash}")
        
    except Exception as e:
        logger.critical(f"Failed to fetch Configuration Manifest from Google Sheets: {e}")
        save_exception_log(run_id=telemetry.run_id, exc_type="FATAL_CONFIG", stack_trace=traceback.format_exc())
        sys.exit(1)
    
    try:
        # STAGE 1: Download/Ingest
        logger.info("Fetching articles from sources...")
        articles = fetch_all_feeds() 
        telemetry.metrics["downloaded"] = len(articles)
        logger.info(f"Ingested {len(articles)} raw articles.")

        # Process Funnel (Injecting the dynamic config_manifest payload)
        for article in articles:
            try:
                process_article(article, telemetry, config_manifest, manifest_hash)
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