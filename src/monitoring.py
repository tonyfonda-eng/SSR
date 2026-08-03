"""
SSR 2.0: Operations Telemetry Engine (DevOps Domain)
Decoupled from Research Telemetry. Tracks runtime health, error rates, 
sensor latency, and cross-run operational infrastructure limits.
"""

import time
import datetime
from collections import defaultdict
import uuid

class MetricsCollector:
    _instance = None

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = MetricsCollector()
        return cls._instance

    def __init__(self):
        self.reset()
        self.settings = {}

    def set_settings(self, settings: dict):
        self.settings = settings

    def reset(self):
        self.run_id = f"SSR-OP-{datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%d%H%M')}-{uuid.uuid4().hex[:6]}"
        self.workflow_start = time.perf_counter()
        
        # In SSR 2.0, article tracking is committed directly to the database via Evidence Capsules.
        # This dictionary is maintained purely for backward compatibility with legacy metrics interfaces 
        # and simple end-of-run counts.
        self.article_traces = {} 
        
        # Operational aggregates
        self.daily = {
            "run_id": self.run_id,
            "downloaded": 0,
            "duplicate_id": 0,
            "empty_body": 0,
            "duplicate_issuer": 0,
            "global_exclusion": 0,
            "rules_rejected": 0,
            "reached_ai": 0,
            "ai_exhausted": 0,
            "ai_rejected_private": 0,
            "ai_rejected_false_positive": 0,
            "playbook_rejected": 0,
            "duplicate_event": 0,
            "alerts_sent": 0,
            "errors": 0,
            "total_runtime_s": 0.0,
            "health_score": 100.0,
            "validation_status": "PENDING",
            "system_confidence": 0.0,
            "db_status": "OK",
            "ai_status": "OK",
            "feed_health_status": "OK",
            "queue_status": "OK",
            "scheduler_status": "RUNNING",
            "gh_actions_status": "OK"
        }
        
        # Cross-sectional operational aggregates
        self.source_stats = defaultdict(lambda: defaultdict(int))
        self.ai_telemetry = defaultdict(lambda: {
            "provider": "unknown", "key_id": "unknown", "requests": 0, "success": 0, "failures": 0,
            "errors_429": 0, "errors_503": 0, "timeouts": 0, "retries": 0, "fallbacks": 0,
            "response_time_sum": 0.0, "max_latency": 0.0, "last_success_ts": "", "last_failure_ts": ""
        })
        self.exceptions = []
        self.funnel = defaultdict(int)

    def track_funnel(self, stage: str, count: int = 1):
        """
        Increments operational aggregate counters.
        Note: The actual Causal Lineage of these drops is recorded instantly in the DB via EvidenceCapsules.
        """
        self.funnel[stage] += count
        if stage in self.daily:
            self.daily[stage] += count

    def log_error(self, module: str, message: str, exc_info=None):
        """Logs infrastructure errors (not research dropouts) into the devops bucket."""
        self.daily["errors"] += 1
        self.exceptions.append({
            "timestamp": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S GMT"),
            "module": module,
            "func_name": "unknown",
            "exc_type": type(exc_info).__name__ if exc_info else "Error",
            "stack_trace": str(exc_info) if exc_info else message,
            "article_url": "",
            "severity": "ERROR"
        })

    def log_ai_request(self, provider: str, key_id: str, success: bool, latency: float, error_code: int = None, is_retry: bool = False, is_fallback: bool = False):
        """Monitors external LLM vendor health, rate limits, and latency spikes."""
        now_ts = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S GMT")
        stats = self.ai_telemetry[key_id]
        
        stats["provider"] = provider
        stats["key_id"] = key_id
        stats["requests"] += 1
        stats["response_time_sum"] += latency
        
        if latency > stats["max_latency"]:
            stats["max_latency"] = latency
            
        if success:
            stats["success"] += 1
            stats["last_success_ts"] = now_ts
        else:
            stats["failures"] += 1
            stats["last_failure_ts"] = now_ts
            if error_code == 429: stats["errors_429"] += 1
            elif error_code == 503: stats["errors_503"] += 1
            else: stats["timeouts"] += 1
            
        if is_retry: stats["retries"] += 1
        if is_fallback: stats["fallbacks"] += 1

    def log_article(self, article_id: str, source: str, url: str, title: str, country: str, language: str,
                    document_type: str, issuer: str, event_family: str, pipeline_stage: str, outcome: str, 
                    reason: str, ai_invoked: bool, processing_time_ms: float, slowest_stage: str):
        """
        Legacy stub to prevent backward-compatibility breaks with older scraper test scripts.
        In SSR 2.0, actual decision tracking executes inside monitor.py via `commit_decision_capsule`.
        """
        self.article_traces[article_id] = {
            "timestamp": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S GMT"),
            "source": source,
            "url": url,
            "title": title,
            "country": country,
            "language": language,
            "document_type": document_type,
            "issuer": issuer,
            "event_family": event_family,
            "pipeline_stage": pipeline_stage,
            "outcome": outcome,
            "reason": reason,
            "ai_invoked": ai_invoked,
            "processing_time_ms": processing_time_ms,
            "slowest_stage": slowest_stage
        }
        
        if source not in self.source_stats:
             self.source_stats[source] = defaultdict(int)
             
        stats = self.source_stats[source]
        stats["processed_count"] += 1
        stats["processing_time_sum"] += processing_time_ms
        
        if outcome == "Alert Sent" or outcome == "DISPATCHED":
            stats["alerts"] += 1
        elif pipeline_stage == "AI Classification" or pipeline_stage == "Financial Verification":
             stats["reached_ai"] += 1
        elif pipeline_stage == "Rules Engine" and outcome != "DROPPED":
             stats["survived_rules"] += 1
        elif pipeline_stage == "Ontology" and outcome != "DROPPED":
             stats["survived_ontology"] += 1
        elif pipeline_stage == "Global Exclusions" and outcome != "DROPPED":
             stats["survived_regex"] += 1

    def calculate_health_score(self, total_runtime_s: float):
        """
        Generates an infrastructure health score (0-100) based strictly on DevOps parameters,
        not Alpha capture performance.
        """
        score = 100.0
        
        if self.daily["errors"] > 0:
            score -= (self.daily["errors"] * 5)
            self.daily["db_status"] = "DEGRADED"
            
        if self.funnel.get("downloaded", 0) == 0:
            score -= 20
            self.daily["feed_health_status"] = "DOWN"
            
        if self.funnel.get("ai_exhausted", 0) > 0:
            score -= 50
            self.daily["ai_status"] = "DOWN"
            
        # Target threshold parameter logic for extreme slow-downs
        if total_runtime_s > 600: 
            score -= 10
            
        self.daily["health_score"] = max(0.0, score)