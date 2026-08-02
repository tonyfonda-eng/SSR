import time
from src.config import SYSTEM_SETTINGS

class PipelineFunnel:
    def __init__(self):
        # Waterfall Pipeline Stages
        self.stages = {
            "downloaded": 0,
            "issuer_duplicate": 0,
            "global_exclusion": 0,
            "regex_rejected": 0,
            "ontology_rejected": 0,
            "rules_rejected": 0,
            "ticker_rejected": 0,
            "ai_classified": 0,
            "playbook_rejected": 0,
            "email_sent": 0
        }
        
        # Terminal Accounting States
        self.terminal = {
            "alerted": 0,
            "rejected": 0,
            "errored": 0
        }

    def record_stage(self, stage_name, count=1):
        if stage_name in self.stages:
            self.stages[stage_name] += count

    def record_terminal(self, state, count=1):
        if state in self.terminal:
            self.terminal[state] += count

    def reconcile(self):
        base = self.stages["downloaded"]
        terminal_sum = sum(self.terminal.values())
        
        print("\n" + "="*55)
        print("          PIPELINE WATERFALL & ACCOUNTING          ")
        print("="*55)
        
        def fmt_stage(label, key):
            count = self.stages[key]
            pct = (count / base * 100) if base > 0 else 0.0
            return f"{label:<25} {count:>8,} ({pct:>5.1f}%)"

        print(fmt_stage("Downloaded", "downloaded"))
        print(f"  ↓ {fmt_stage('Issuer Duplicate', 'issuer_duplicate')}")
        print(f"  ↓ {fmt_stage('Global Exclusion', 'global_exclusion')}")
        print(f"  ↓ {fmt_stage('Regex Rejected', 'regex_rejected')}")
        print(f"  ↓ {fmt_stage('Ontology Rejected', 'ontology_rejected')}")
        print(f"  ↓ {fmt_stage('Rules Rejected', 'rules_rejected')}")
        print(f"  ↓ {fmt_stage('Ticker Validation', 'ticker_rejected')}")
        print(f"  ↓ {fmt_stage('AI Classified', 'ai_classified')}")
        print(f"  ↓ {fmt_stage('Playbook Rejected', 'playbook_rejected')}")
        print(f"  ↓ {fmt_stage('Email Sent', 'email_sent')}")
        print("-" * 55)
        
        print(f"TERMINAL STATES:")
        print(f"  Alerted:  {self.terminal['alerted']:>8,}")
        print(f"  Rejected: {self.terminal['rejected']:>8,}")
        print(f"  Errored:  {self.terminal['errored']:>8,}")
        print("="*55)

        if base != terminal_sum:
            penalty = SYSTEM_SETTINGS.get("ACCOUNTING_FAILURE_PENALTY", 40)
            print("\n⚠️ [CRITICAL ACCOUNTING ERROR] ⚠️")
            print(f"  Invariant Violation: Downloaded ({base}) != Terminal Sum ({terminal_sum})")
            print(f"  [HEALTH MODIFIER] Health Score -= {penalty}. Alert Triggered.\n")
        else:
            print("✅ State Reconciliation: PASSED (100% Accounted For)\n")
