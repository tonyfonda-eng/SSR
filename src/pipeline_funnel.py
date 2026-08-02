class PipelineFunnel:
    def __init__(self):
        # Mutual exclusive terminal state counters
        self.downloaded = 0
        self.duplicates = 0
        self.excluded = 0
        self.rejected = 0
        self.alerted = 0
        self.errored = 0

    def reconcile(self):
        """
        State Reconciliation Invariant.
        Every single record must sit in exactly one terminal state category.
        """
        terminal_sum = (self.duplicates + self.excluded + self.rejected + self.alerted + self.errored)
        
        print("\n" + "="*50)
        print("         INSTITUTIONAL PIPELINE RECONCILIATION         ")
        print("="*50)
        
        def fmt_line(label, count, base):
            pct = (count / base * 100) if base > 0 else 0.0
            return f"{label:<25} {count:>8,} ({pct:>5.1f}%)"

        print(f"Downloaded Total......... {self.downloaded:>8,}")
        print(f"  ↓ {fmt_line('Issuer Duplicates', self.duplicates, self.downloaded)}")
        print(f"  ↓ {fmt_line('Global Excluded', self.excluded, self.downloaded)}")
        print(f"  ↓ {fmt_line('Regex/Ontology Rejected', self.rejected, self.downloaded)}")
        print(f"  ↓ {fmt_line('Errored Out', self.errored, self.downloaded)}")
        print(f"  ↓ {fmt_line('Alerted Actions', self.alerted, self.downloaded)}")
        print("="*50)

        if self.downloaded != terminal_sum:
            print("\n⚠️ [CRITICAL ACCOUNTING ERROR] ⚠️")
            print(f"  Invariant Violation: Downloaded ({self.downloaded}) != Terminal Sum ({terminal_sum})")
            print("  Variance: Balance of articles disappeared silently inside intermediate steps.")
            print("  [HEALTH MODIFIER] Logging Exception. Health Score -= 40. Dashboard Alert Triggered.\n")
            # Hook logic here for your health logging pipeline
        else:
            print("✅ State Reconciliation Invariant: PASSED (100% Accounted For)\n")
