import unittest
import json
import sqlite3
import os
import datetime
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent))
from src.audit import monday_acceptance
from src.audit.monday_acceptance import generate_monday_report

class TestAcceptanceAuditorAdversarial(unittest.TestCase):
    def setUp(self):
        self.test_dir = Path(__file__).resolve().parent / "test_data"
        self.test_dir.mkdir(exist_ok=True)
        self.test_db_path = self.test_dir / "audit.db"
        self.test_evidence = self.test_dir / "evidence.json"
        self.test_report = self.test_dir / "report.md"
        
        from unittest.mock import patch, mock_open
        self.patcher = patch('src.audit.monday_acceptance.AUDIT_DB_PATH', str(self.test_db_path))
        self.patcher.start()
        
        self.ledger_file = self.test_dir / "ingestion_ledger.json"
        with open(self.ledger_file, "w") as f:
            json.dump([], f)
        
        # Patch the ledger path in monday_acceptance if it's hardcoded
        # Actually it's hardcoded as 'docs/ingestion_ledger.json'
        # We can just patch open for that specific file.
        import builtins
        self.original_open = builtins.open
        def mocked_open(path, *args, **kwargs):
            if str(path).endswith('ingestion_ledger.json'):
                return self.original_open(self.ledger_file, *args, **kwargs)
            return self.original_open(path, *args, **kwargs)
        self.open_patcher = patch('builtins.open', side_effect=mocked_open)
        self.open_patcher.start()
        
        # Initialize test DB
        if self.test_db_path.exists():
            self.test_db_path.unlink()
        
        conn = sqlite3.connect(self.test_db_path)
        c = conn.cursor()
        c.execute('''
            CREATE TABLE IF NOT EXISTS daily_source_metrics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT,
                source TEXT,
                channel TEXT,
                raw_found INTEGER,
                unique_found INTEGER,
                valid_url_count INTEGER,
                valid_title_count INTEGER,
                valid_body_count INTEGER,
                emergency_stop INTEGER DEFAULT 0,
                entered_dedupe_count INTEGER DEFAULT 0,
                dedupe_passed_count INTEGER DEFAULT 0,
                dedupe_rejected_count INTEGER DEFAULT 0,
                ingestion_ledger_json TEXT
            )
        ''')
        
        c.execute('''
            CREATE TABLE IF NOT EXISTS article_screening_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT,
                source TEXT,
                article_url TEXT,
                ingestion_mode TEXT,
                outcome TEXT,
                final_stage TEXT,
                drop_reason TEXT,
                body_sha256 TEXT
            )
        ''')
        conn.commit()
        self.conn = conn
        
    def tearDown(self):
        self.conn.close()
        self.patcher.stop()
        self.open_patcher.stop()
        if self.test_db_path.exists():
            self.test_db_path.unlink()
        if self.test_evidence.exists():
            self.test_evidence.unlink()
        if self.test_report.exists():
            self.test_report.unlink()
        if self.ledger_file.exists():
            self.ledger_file.unlink()

    def _insert_metric(self, source, raw_found, unique_found, entered_dedupe, passed, rejected, ledger_json, timestamp=None):
        ts = timestamp or datetime.datetime.now(datetime.timezone.utc).isoformat()
        c = self.conn.cursor()
        c.execute('''
            INSERT INTO daily_source_metrics 
            (timestamp, source, channel, raw_found, unique_found, valid_url_count, valid_title_count, valid_body_count, entered_dedupe_count, dedupe_passed_count, dedupe_rejected_count, ingestion_ledger_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (ts, source, "TEST", raw_found, unique_found, raw_found, raw_found, raw_found, entered_dedupe, passed, rejected, json.dumps(ledger_json)))
        self.conn.commit()
        
        # Also append to ledger file
        with self.original_open(self.ledger_file, "r") as f:
            ledger_data = json.load(f)
        
        ledger_entry = ledger_json.copy()
        ledger_entry["source"] = source
        ledger_entry["timestamp"] = ts
        ledger_data.append(ledger_entry)
        
        # Need to use the original builtins.open to write to avoid infinite recursion or just rely on the mock working properly.
        # The mock does pass through if the file is our target file.
        with self.original_open(self.ledger_file, "w") as f:
            json.dump(ledger_data, f)

    def test_adversarial_1_http200_empty_result_no_exhaustion(self):
        ledger = {"termination_reason": "UNEXPLAINED_TERMINATION"}
        self._insert_metric("NewsWeb (Norway)", 0, 0, 0, 0, 0, ledger)
        # Should exit 1 due to NO-GO (UNEXPLAINED_TERMINATION is not in valid_terminations)
        with self.assertRaises(SystemExit) as cm:
            generate_monday_report(["NewsWeb (Norway)"], str(self.test_report), str(self.test_evidence))
        self.assertEqual(cm.exception.code, 1)

    def test_adversarial_2_http200_parser_exception(self):
        ledger = {"termination_reason": "PARSER_ERROR"}
        self._insert_metric("NewsWeb (Norway)", 0, 0, 0, 0, 0, ledger)
        with self.assertRaises(SystemExit) as cm:
            generate_monday_report(["NewsWeb (Norway)"], str(self.test_report), str(self.test_evidence))
        self.assertEqual(cm.exception.code, 1)

    def test_adversarial_3_http403_empty_result(self):
        ledger = {"termination_reason": "HTTP_403"}
        self._insert_metric("NewsWeb (Norway)", 0, 0, 0, 0, 0, ledger)
        with self.assertRaises(SystemExit) as cm:
            generate_monday_report(["NewsWeb (Norway)"], str(self.test_report), str(self.test_evidence))
        self.assertEqual(cm.exception.code, 1)
        
    def test_adversarial_5_arbitrary_limit_reached(self):
        ledger = {"termination_reason": "ARBITRARY_LIMIT_REACHED"}
        self._insert_metric("NewsWeb (Norway)", 100, 100, 100, 100, 0, ledger)
        with self.assertRaises(SystemExit) as cm:
            generate_monday_report(["NewsWeb (Norway)"], str(self.test_report), str(self.test_evidence))
        self.assertEqual(cm.exception.code, 1)

    def test_adversarial_6_legitimate_exhaustion_pass(self):
        ledger = {"termination_reason": "SUCCESS_EXHAUSTED", "exhaustion_evidence": "valid"}
        self._insert_metric("NewsWeb (Norway)", 100, 100, 100, 100, 0, ledger)
        # Should not raise SystemExit!
        try:
            generate_monday_report(["NewsWeb (Norway)"], str(self.test_report), str(self.test_evidence))
        except SystemExit:
            self.fail("generate_monday_report exited unexpectedly on a PASS condition.")

    def test_adversarial_7_missing_telemetry(self):
        # Empty DB for "NewsWeb (Norway)"
        with self.assertRaises(SystemExit) as cm:
            generate_monday_report(["NewsWeb (Norway)"], str(self.test_report), str(self.test_evidence))
        self.assertEqual(cm.exception.code, 1)

    def test_adversarial_10_conservation_mismatch(self):
        ledger = {"termination_reason": "SUCCESS_EXHAUSTED", "exhaustion_evidence": "valid"}
        # 100 valid payloads, but only 90 NEW + 5 DUP (5 unaccounted)
        self._insert_metric("NewsWeb (Norway)", 100, 100, 100, 90, 5, ledger)
        with self.assertRaises(SystemExit) as cm:
            generate_monday_report(["NewsWeb (Norway)"], str(self.test_report), str(self.test_evidence))
        self.assertEqual(cm.exception.code, 1)

    def test_adversarial_11_forged_success_state(self):
        ledger = {"termination_reason": "SUCCESS_EXHAUSTED", "exhaustion_evidence": "missing"}
        self._insert_metric("NewsWeb (Norway)", 0, 0, 0, 0, 0, ledger)
        with self.assertRaises(SystemExit) as cm:
            generate_monday_report(["NewsWeb (Norway)"], str(self.test_report), str(self.test_evidence))
        self.assertEqual(cm.exception.code, 1)

    def test_adversarial_12_false_exhaustion(self):
        ledger = {"termination_reason": "SUCCESS_EXHAUSTED", "exhaustion_evidence": "valid", "pagination": {"has_next_page": True}}
        self._insert_metric("NewsWeb (Norway)", 100, 100, 100, 100, 0, ledger)
        with self.assertRaises(SystemExit) as cm:
            generate_monday_report(["NewsWeb (Norway)"], str(self.test_report), str(self.test_evidence))
        self.assertEqual(cm.exception.code, 1)

if __name__ == '__main__':
    unittest.main()
