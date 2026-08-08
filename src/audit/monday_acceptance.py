import sqlite3
import json
import datetime
import os
import hashlib
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent.parent))
from src.database import _get_connection, AUDIT_DB_PATH, RESEARCH_DB_PATH
from src.sheets import load_sources
from src.config.settings import SHEET_URL

def generate_monday_report(override_sources=None, out_file=None, evidence_file=None):
    today = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d")
    out_dir = Path("docs/daily_audit")
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_file or (out_dir / f"{today}_monday_acceptance.md")
    evidence_file = evidence_file or (out_dir / f"{today}_monday_completeness_evidence.json")
    
    # 1. Fetch Google Sheets Configured Sources
    try:
        if override_sources is not None:
            enabled_sources = override_sources
        else:
            configured_sources_raw = load_sources(SHEET_URL)
            enabled_sources = [s.get("Source Name", s.get("Source", "Unknown")) for s in configured_sources_raw if str(s.get("Enabled", "")).upper() in ["YES", "TRUE"]]
    except Exception as e:
        print(f"FAILED ACCEPTANCE. Could not reach Control Plane (Google Sheets) to verify enabled sources: {e}", file=sys.stderr)
        sys.exit(1)
        
    audit_conn = _get_connection(AUDIT_DB_PATH)
    research_conn = _get_connection(RESEARCH_DB_PATH)
    audit_conn.row_factory = sqlite3.Row
    research_conn.row_factory = sqlite3.Row
    
    try:
        with open("docs/ingestion_ledger.json", "r") as f:
            ledger = json.load(f)
            today_ledger = [x for x in ledger if x.get("timestamp", "").startswith(today)]
    except Exception:
        today_ledger = []
        
    c_audit = audit_conn.cursor()
    c_res = research_conn.cursor()
    
    # Pre-fetch metrics
    c_audit.execute("""
        SELECT source, SUM(raw_found) as raw, SUM(unique_found) as uniq,
               SUM(valid_url_count) as valid_url, SUM(valid_title_count) as valid_title,
               SUM(valid_body_count) as valid_body, MAX(emergency_stop) as em_stop,
               SUM(entered_dedupe_count) as entered_dedupe,
               SUM(dedupe_passed_count) as dedupe_passed, SUM(dedupe_rejected_count) as dedupe_rejected
        FROM daily_source_metrics
        WHERE substr(timestamp, 1, 10) = ?
        GROUP BY source
    """, (today,))
    db_metrics = {r['source']: dict(r) for r in c_audit.fetchall()}
    
    evidence_objects = []
    
    for src in enabled_sources:
        # Build the Source Completeness Evidence Object
        ledger_entries = [e for e in today_ledger if e.get("source") == src]
        latest_ledger = sorted(ledger_entries, key=lambda x: x.get("timestamp", ""))[-1] if ledger_entries else {}
        db_m = db_metrics.get(src, {})
        
        meta = latest_ledger.get("metadata", {})
        raw_discovered = db_m.get("raw", 0) or 0
        valid_payloads = db_m.get("entered_dedupe", 0) or 0
        invalid_payloads = raw_discovered - valid_payloads
        
        new_c = db_m.get("dedupe_passed", 0) or 0
        dup_c = db_m.get("dedupe_rejected", 0) or 0
        
        # Verify termination condition
        term_reason = latest_ledger.get("termination_reason", "NO_LEDGER_ENTRY")
        exhaustion_evidence = latest_ledger.get("exhaustion_evidence")
        has_next_page = latest_ledger.get("pagination", {}).get("has_next_page", False)
        
        valid_terminations = ["SUCCESS_EXHAUSTED", "SUCCESS_CHECKPOINT", "SUCCESS_PUBLICATION_WINDOW_REACHED"]
        
        unaccounted = valid_payloads - (new_c + dup_c)
        status = "PASS"
        if term_reason not in valid_terminations or unaccounted != 0 or db_m.get("em_stop") or not ledger_entries:
            status = "FAIL"
        elif exhaustion_evidence != "valid":
            status = "FAIL"
        elif has_next_page:
            status = "FAIL"
            
        # Classify zero-result sources explicitly
        empty_classification = "N/A"
        if raw_discovered == 0:
            if status == "PASS" and exhaustion_evidence == "valid":
                empty_classification = "LEGITIMATELY_EMPTY"
            else:
                empty_classification = "BROKEN/NOT_TESTABLE"
                status = "FAIL"
                
        evidence = {
            "source": src,
            "enabled": True,
            "scraper": latest_ledger.get("resolved_adapter", "UNKNOWN"),
            "endpoint": latest_ledger.get("configured_url", "UNKNOWN"),
            "http_status": meta.get("http_status", 200) if term_reason != "NO_LEDGER_ENTRY" else "UNKNOWN",
            "waf_events": meta.get("waf_events", 0),
            "rate_limit_events": meta.get("rate_limit_events", 0),
            "parser_errors": meta.get("parser_errors", 0),
            "pages_attempted": meta.get("pages_attempted", latest_ledger.get("pages_scanned", 0)),
            "pages_successful": meta.get("pages_successful", latest_ledger.get("pages_scanned", 0)),
            "pagination_cursor_start": meta.get("pagination_cursor_start", ""),
            "pagination_cursor_end": meta.get("pagination_cursor_end", ""),
            "termination_reason": term_reason,
            "items_discovered": raw_discovered,
            "items_extracted": valid_payloads,
            "extraction_failures": invalid_payloads,
            "empty_title_count": raw_discovered - (db_m.get("valid_title", 0) or 0),
            "empty_body_count": raw_discovered - (db_m.get("valid_body", 0) or 0),
            "invalid_url_count": raw_discovered - (db_m.get("valid_url", 0) or 0),
            "first_publication_timestamp": latest_ledger.get("oldest_article_seen", ""),
            "last_publication_timestamp": latest_ledger.get("newest_article_seen", ""),
            "new_count": new_c,
            "duplicate_count": dup_c,
            "audit_status": status,
            "empty_classification": empty_classification
        }
        evidence_objects.append(evidence)
        
    with open(evidence_file, "w", encoding="utf-8") as f:
        json.dump(evidence_objects, f, indent=2)

    # Halt on Failure - The Adaptive Repair Directive
    failures = [e for e in evidence_objects if e["audit_status"] == "FAIL"]
    if failures:
        print("\n================ ADAPTIVE REPAIR DIRECTIVE ================", file=sys.stderr)
        for f in failures:
            reason = f["termination_reason"]
            if f["items_discovered"] > 0 and f["new_count"] + f["duplicate_count"] != f["items_extracted"]:
                reason = "UNACCOUNTED_LEAKAGE"
            print(f"{f['source'].upper()} FAILED ACCEPTANCE ({reason}). DO NOT PRODUCE A REPORT. INVESTIGATE THE FAILURE, IDENTIFY AN ALTERNATIVE ACQUISITION METHOD, IMPLEMENT IT, AND RE-RUN THE SOURCE BATTERY.", file=sys.stderr)
        print("===========================================================\n", file=sys.stderr)
        sys.exit(1)
        
    md = []
    today_date = datetime.datetime.now(datetime.timezone.utc)
    day_name = today_date.strftime("%A").upper()
    md.append(f"# SSR INGESTION ACCEPTANCE — {day_name} ({today})\n")
    
    total_discovered = sum(e['items_discovered'] for e in evidence_objects)
    total_valid = sum(e['items_extracted'] for e in evidence_objects)
    total_invalid = sum(e['extraction_failures'] for e in evidence_objects)
    total_unacc = total_discovered - (total_valid + total_invalid)
    
    total_new = sum(e['new_count'] for e in evidence_objects)
    total_dup = sum(e['duplicate_count'] for e in evidence_objects)
    dedupe_unacc = total_valid - (total_new + total_dup)
    
    empty_sha256 = hashlib.sha256(b"").hexdigest()
    c_res.execute("SELECT COUNT(*) as c FROM article_screening_log WHERE body_sha256 = ?", (empty_sha256,))
    empty_body_count = c_res.fetchone()['c']
    
    total_untitled = sum(e['empty_title_count'] for e in evidence_objects)
    
    go_no_go = "GO" if len(failures) == 0 and total_unacc == 0 and dedupe_unacc == 0 and empty_body_count == 0 else "NO-GO"
    
    md.append("```text")
    md.append(f"Enabled sources:       {len(evidence_objects)}")
    md.append(f"Sources PASS:          {len(evidence_objects) - len(failures)}")
    md.append(f"Sources FAIL:          {len(failures)}")
    md.append("")
    md.append(f"Articles discovered:   {total_discovered}")
    md.append(f"Valid payloads:        {total_valid}")
    md.append(f"Extraction failures:   {total_invalid}")
    md.append(f"Unaccounted:           {total_unacc}")
    md.append("")
    md.append(f"Dedupe NEW:            {total_new}")
    md.append(f"Dedupe DUPLICATE:      {total_dup}")
    md.append(f"Dedupe unaccounted:    {dedupe_unacc}")
    md.append("")
    md.append(f"EMPTY-BODY HASHES:     {empty_body_count}")
    md.append(f"UNTITLED ARTICLES:     {total_untitled}")
    md.append("")
    md.append(f"GO / NO-GO:            {go_no_go}")
    md.append("```")
    md.append("\n")
    
    if failures:
        for f in failures:
            md.append(f"### FAILED SOURCE: {f['source']}")
            reason = f["termination_reason"]
            if f["items_discovered"] > 0 and f["new_count"] + f["duplicate_count"] != f["items_extracted"]:
                reason = "UNACCOUNTED_LEAKAGE"
            md.append(f"**Reason:**\n{reason}\n")
            md.append(f"**Articles acquired:**\n{f['items_discovered']}\n")
            md.append("**Completeness:**\nUNPROVEN\n")
            md.append("**Directive:**")
            md.append("> DO NOT PRODUCE A REPORT.")
            md.append("> INVESTIGATE ALTERNATIVE ACQUISITION METHOD.")
            md.append("> FIX.")
            md.append("> RERUN SOURCE BATTERY.\n")
            
    md.append("## Source-by-Source Data")
    md.append("| Source | Discovered | Valid | Extraction Fail | NEW | DUP | Unaccounted | First Pub | Last Pub | Pages/Cursors | Termination | Errors | Status |")
    md.append("|---|---|---|---|---|---|---|---|---|---|---|---|---|")
    for e in evidence_objects:
        unacc = e['items_extracted'] - (e['new_count'] + e['duplicate_count'])
        pages = f"{e['pages_successful']}/{e['pages_attempted']}"
        wafs = f"{e['waf_events']}/{e['parser_errors']}"
        first_p = str(e['first_publication_timestamp'])[:10] if e['first_publication_timestamp'] else "-"
        last_p = str(e['last_publication_timestamp'])[:10] if e['last_publication_timestamp'] else "-"
        md.append(f"| {e['source']} | {e['items_discovered']} | {e['items_extracted']} | {e['extraction_failures']} | {e['new_count']} | {e['duplicate_count']} | {unacc} | {first_p} | {last_p} | {pages} | {e['termination_reason']} | {wafs} | **{e['audit_status']}** |")
    md.append("\n")
    
    with open(out_file, "w", encoding="utf-8") as f:
        f.write("\n".join(md))
        
    print(f"Monday Acceptance Report written to {out_file}")
    print(f"Machine-readable Evidence Object written to {evidence_file}")

if __name__ == "__main__":
    generate_monday_report()
