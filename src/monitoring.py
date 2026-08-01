import time
import datetime
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
        self.workflow_start = time.perf_counter()
        
        # Timings
        self.timings = {
            "download": 0.0,
            "regex": 0.0,
            "rules": 0.0,
            "ai_classification": 0.0,
            "playbook": 0.0,
            "email": 0.0
        }
        
        self.daily = {
            "downloaded": 0,
            "unique": 0,
            "duplicates": 0,
            "passed_regex": 0,
            "failed_regex": 0,
            "global_exclusions": 0,
            "ontology_matches": 0,
            "rules_passes": 0,
            "rules_failures": 0,
            "ai_calls": 0,
            "ai_successes": 0,
            "ai_failures": 0,
            "playbooks_executed": 0,
            "emails_sent": 0,
            "rules_score_sum": 0.0,
            "ai_confidence_sum": 0.0,
            "articles_processed_count": 0,
            "article_times": [],
            "anomalies": set()
        }
        
        # Source -> metrics
        self.source_stats = defaultdict(lambda: {
            "downloaded": 0,
            "survived_regex": 0,
            "survived_rules": 0,
            "reached_ai": 0,
            "alerts": 0,
            "processing_time_sum": 0.0,
            "processed_count": 0
        })
        
        # key_id -> metrics
        self.ai_telemetry = defaultdict(lambda: {
            "provider": "",
            "key_id": "",
            "requests": 0,
            "success": 0,
            "failures": 0,
            "429_errors": 0,
            "503_errors": 0,
            "timeouts": 0,
            "retries": 0,
            "fallbacks": 0,
            "response_time_sum": 0.0,
            "last_used": ""
        })
        
        self.article_traces = {}

    def track_time(self, category, duration):
        if category in self.timings:
            self.timings[category] += duration

    def log_article(self, article_id, source, url, title, country, language, document_type, issuer, event_family, stage, final_status, drop_reason, processing_time_ms):
        self.article_traces[article_id] = {
            "timestamp": datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC"),
            "source": source or "Unknown",
            "url": url or "",
            "title": title or "",
            "country": country or "",
            "language": language or "",
            "document_type": document_type or "",
            "issuer": issuer or "",
            "event_family": event_family or "",
            "stage": stage or "Unknown",
            "final_status": final_status or "",
            "drop_reason": drop_reason or "",
            "processing_time_ms": int(processing_time_ms)
        }
        
        # Update run stats
        self.daily["articles_processed_count"] += 1
        self.daily["article_times"].append(processing_time_ms)
        self.source_stats[source]["processing_time_sum"] += processing_time_ms
        self.source_stats[source]["processed_count"] += 1

    def log_ai_usage(self, provider, key_id, success, is_429=False, is_503=False, is_timeout=False, is_retry=False, is_fallback=False, response_time=0.0):
        entry = self.ai_telemetry[key_id]
        entry["provider"] = provider
        entry["key_id"] = key_id
        entry["requests"] += 1
        if success:
            entry["success"] += 1
        else:
            entry["failures"] += 1
            
        if is_429: entry["429_errors"] += 1
        if is_503: entry["503_errors"] += 1
        if is_timeout: entry["timeouts"] += 1
        if is_retry: entry["retries"] += 1
        if is_fallback: entry["fallbacks"] += 1
        
        entry["response_time_sum"] += response_time
        entry["last_used"] = datetime.datetime.utcnow().strftime("%H:%M:%S UTC")
        
        self.daily["ai_calls"] += 1
        if success:
            self.daily["ai_successes"] += 1
        else:
            self.daily["ai_failures"] += 1
