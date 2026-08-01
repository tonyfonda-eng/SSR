import time
import datetime
import os
import sys
from collections import defaultdict

class MetricsCollector:
    _instance = None
    
    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = MetricsCollector()
        return cls._instance
        
    def __init__(self):
        self.reset()
        
    def reset(self):
        self.run_id = os.environ.get("GITHUB_RUN_ID", datetime.datetime.utcnow().strftime("%Y%m%d%H%M%S"))
        self.workflow_start = time.perf_counter()
        
        self.daily = {
            "downloaded": 0, "unique": 0, "duplicates": 0, "passed_regex": 0, "failed_regex": 0,
            "global_exclusions": 0, "ontology_matches": 0, "rules_passes": 0, "rules_failures": 0,
            "ai_calls": 0, "ai_successes": 0, "ai_failures": 0, "playbooks_executed": 0, "emails_sent": 0,
            "rules_score_sum": 0.0, "ai_confidence_sum": 0.0, "articles_processed_count": 0,
            "articles_skipped_before_ai": 0
        }
        
        # Source -> metrics
        self.source_stats = defaultdict(lambda: {
            "downloaded": 0, "survived_regex": 0, "survived_ontology": 0, "survived_rules": 0,
            "reached_ai": 0, "alerts": 0, "processing_time_sum": 0.0, "processed_count": 0
        })
        
        # key_id -> metrics
        self.ai_telemetry = defaultdict(lambda: {
            "provider": "", "key_id": "", "requests": 0, "success": 0, "failures": 0,
            "errors_429": 0, "errors_503": 0, "timeouts": 0, "retries": 0, "fallbacks": 0,
            "response_time_sum": 0.0, "max_latency": 0.0, "last_success_ts": "", "last_failure_ts": ""
        })
        
        self.article_traces = {}
        self.exceptions = []

    def log_article(self, article_id, source, url, title, country, language, document_type, issuer, event_family, pipeline_stage, outcome, reason, ai_invoked, processing_time_ms):
        self.article_traces[article_id] = {
            "timestamp": datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC"),
            "source": source or "Unknown", "url": url or "", "title": title or "",
            "country": country or "", "language": language or "", "document_type": document_type or "",
            "issuer": issuer or "", "event_family": event_family or "",
            "pipeline_stage": pipeline_stage or "Unknown", "outcome": outcome or "",
            "reason": reason or "", "ai_invoked": 1 if ai_invoked else 0, "processing_time_ms": int(processing_time_ms)
        }
        
        # Update run stats
        self.daily["articles_processed_count"] += 1
        self.source_stats[source]["processing_time_sum"] += processing_time_ms
        self.source_stats[source]["processed_count"] += 1
        
        if not ai_invoked:
            self.daily["articles_skipped_before_ai"] += 1

    def log_ai_usage(self, provider, key_id, success, is_429=False, is_503=False, is_timeout=False, is_retry=False, is_fallback=False, response_time=0.0):
        entry = self.ai_telemetry[key_id]
        entry["provider"] = provider
        entry["key_id"] = key_id
        entry["requests"] += 1
        
        if response_time > entry["max_latency"]:
            entry["max_latency"] = response_time
            
        now_ts = datetime.datetime.utcnow().strftime("%H:%M:%S UTC")
        
        if success:
            entry["success"] += 1
            entry["last_success_ts"] = now_ts
        else:
            entry["failures"] += 1
            entry["last_failure_ts"] = now_ts
            
        if is_429: entry["errors_429"] += 1
        if is_503: entry["errors_503"] += 1
        if is_timeout: entry["timeouts"] += 1
        if is_retry: entry["retries"] += 1
        if is_fallback: entry["fallbacks"] += 1
        
        entry["response_time_sum"] += response_time
        
        self.daily["ai_calls"] += 1
        if success: self.daily["ai_successes"] += 1
        else: self.daily["ai_failures"] += 1

    def log_exception(self, exc_type, stack_trace, module, func_name, article_url=""):
        self.exceptions.append({
            "run_id": self.run_id,
            "timestamp": datetime.datetime.utcnow().isoformat(),
            "exc_type": exc_type,
            "stack_trace": stack_trace,
            "module": module,
            "func_name": func_name,
            "article_url": article_url
        })
        
    def calculate_health_score(self, total_runtime_s):
        score = 100
        # Deduct for failed AI requests (max -30)
        total_ai_calls = self.daily["ai_calls"]
        if total_ai_calls > 0:
            fail_rate = self.daily["ai_failures"] / total_ai_calls
            score -= int(fail_rate * 30)
            
        # Deduct for exceptions (max -40)
        score -= min(len(self.exceptions) * 10, 40)
        
        # Deduct for long runtime (max -30)
        if total_runtime_s > 180:
            penalty = int((total_runtime_s - 180) / 10)
            score -= min(penalty, 30)
            
        return max(0, score)
