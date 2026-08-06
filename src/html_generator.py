import datetime
import os
import json

# ---------------------------------------------------------------------------
# SSR 2.0 INSTITUTIONAL OPERATIONS CENTRE & DECISION INTELLIGENCE
# ---------------------------------------------------------------------------

AWAITING_SPAN = '<span class="awaiting">Awaiting Data</span>'

def _daily(metrics, key, default=None):
    if isinstance(metrics, dict):
        d = metrics.get("daily", metrics)
        val = d.get(key, default) if isinstance(d, dict) else metrics.get(key, default)
        return val if val is not None else default
    else:
        d = getattr(metrics, "daily", metrics)
        val = d.get(key, default) if isinstance(d, dict) else getattr(d, key, default)
        return val if val is not None else default

def _sub(metrics, group, key, default=None):
    if isinstance(metrics, dict):
        group_val = metrics.get(group, metrics)
        val = group_val.get(key, default) if isinstance(group_val, dict) else metrics.get(key, default)
        return val if val is not None else default
    else:
        group_val = getattr(metrics, group, metrics)
        val = group_val.get(key, default) if isinstance(group_val, dict) else getattr(group_val, key, default)
        return val if val is not None else default

def _bag(value, key, default=None):
    if value is None: return default
    val = value.get(key, default) if isinstance(value, dict) else getattr(value, key, default)
    return val if val is not None else default

def _rows(value):
    if not value: return []
    return list(value) if isinstance(value, (list, tuple)) else []

def esc(value):
    if value is None or value == "": return ""
    return str(value).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")

def is_num(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool)

def safe_div(numerator, denominator):
    if not is_num(numerator) or not is_num(denominator) or denominator == 0: return None
    return numerator / denominator

def fmt_pct(value, decimals=1):
    return f"{value:.{decimals}f}%" if is_num(value) else None

def fmt_num(value, decimals=1):
    if not is_num(value): return None
    return f"{int(value):,}" if isinstance(value, int) or float(value).is_integer() else f"{value:.{decimals}f}"

def status_badge(value, ok_values=("OK", "HEALTHY", "PASS", "UP", "RUNNING", "DETECTED", "DISPATCHED")):
    if not value: return '<span class="badge awaiting">AWAITING DATA</span>'
    v = str(value).upper()
    if v in ok_values: cls = "success"
    elif v in ("DEGRADED", "WARN", "WARNING", "SLOW", "PENDING"): cls = "warn"
    elif v in ("DOWN", "FAIL", "FAILED", "ERROR", "STOPPED", "DROPPED"): cls = "danger"
    else: cls = "info"
    return f'<span class="badge {cls}">{esc(value)}</span>'

# Multi-key stage definitions to support legacy and current drop reasons seamlessly
LOSS_STAGE_DEFS = [
    ("Sensor Ingestion",      ["downloaded"],                                            None,                     "start"),
    ("Idempotency & Dedupe",  ["dropped_hash_duplicate", "duplicate", "duplicate_id"],   "Ingestion",              "loss"),
    ("Global Exclusions",     ["dropped_global_keyword", "exclusion", "global_exclusion", "dropped_issuer_exclusion", "dropped_source_specific_noise"], "Global Exclusions", "loss"),
    ("Ontology Extraction",   ["dropped_ontology_score", "ontology"],                    "ontology_concepts",      "loss"),
    ("Deterministic Rules",   ["dropped_rules_threshold", "rules", "rules_rejected"],    "regex_rules",            "loss"),
    ("Entity Resolution",     ["dropped_entity_confidence", "dropped_entity_missing_ticker", "dropped_entity_unknown_issuer", "dropped_entity_missing_both", "dropped_ai_no_ticker"], "entity_confidence", "loss"),
    ("Financial Verification",["dropped_untradeable_otc", "dropped_financial_t12", "dropped_insufficient_liquidity", "dropped_no_options_chain"], "Financial Verification", "loss"),
    ("AI Strategy Playbook",  ["dropped_ai_confidence", "ai", "ai_exhausted"],           "ai_confidence_gate",     "loss"),
    ("Detected & Dispatched", ["alerts_generated", "alerts", "alerts_sent"],             "AI_APPROVED",            "terminal"),
]

def _get_stage_raw_count(funnel_counts, keys):
    if not isinstance(funnel_counts, dict):
        return None
    for k in keys:
        if k in funnel_counts and is_num(funnel_counts[k]):
            return funnel_counts[k]
    return None

def build_loss_funnel(funnel_counts):
    funnel_counts = funnel_counts if isinstance(funnel_counts, dict) else {}
    total = _get_stage_raw_count(funnel_counts, ["downloaded"])
    have_total = is_num(total)
    entering = total if have_total else None
    rows = []
    
    # We want to extract specific drop reasons from the funnel counts payload
    # In monitor.py, telemetry.stage_analytics maps stage name to a dict with "drop_reasons"
    
    for label, keys, stage_token, kind in LOSS_STAGE_DEFS:
        raw = _get_stage_raw_count(funnel_counts, keys)
        awaiting = raw is None and kind != "start"
        
        specific_reasons = {}
        if kind == "loss":
            # Search funnel_counts for specific drop reasons matching this stage
            for k, v in funnel_counts.items():
                if isinstance(v, dict) and "drop_reasons" in v:
                    # check if the drop reasons in this stage map to the keys
                    for dr_key, dr_val in v["drop_reasons"].items():
                        for candidate in keys:
                            if candidate in dr_key:
                                specific_reasons[dr_key] = specific_reasons.get(dr_key, 0) + dr_val
                                break
                                
            # If the funnel counts is flat
            for dr_key, dr_val in funnel_counts.items():
                if not isinstance(dr_val, dict):
                    for candidate in keys:
                        if candidate in dr_key and dr_key not in ["downloaded", "alerts_generated"]:
                            specific_reasons[dr_key] = dr_val
                            break
        
        if kind == "start":
            exiting = total
            lost = 0
            conv_pct = 100.0 if have_total else None
            loss_pct = 0.0 if have_total else None
            awaiting = not have_total
        elif kind == "terminal":
            lost = 0
            exiting = raw
            conv_pct = safe_div(exiting, entering) * 100 if have_total and is_num(exiting) and is_num(entering) else None
            loss_pct = 0.0 if is_num(conv_pct) else None
        else:
            lost = sum(specific_reasons.values()) if specific_reasons else (raw or 0)
            if is_num(entering) and is_num(lost):
                exiting = entering - lost
                loss_pct = safe_div(lost, entering) * 100 if entering else None
                conv_pct = safe_div(exiting, entering) * 100 if entering else None
            else:
                exiting, conv_pct, loss_pct = None, None, None
                
        rows.append(dict(label=label, entering=entering, exiting=exiting, lost=lost, conv_pct=conv_pct, loss_pct=loss_pct, stage_token=stage_token, kind=kind, awaiting=awaiting, reasons=specific_reasons))
        
        if is_num(exiting):
            entering = exiting
            
    return rows, have_total

def render_loss_funnel_html(funnel_counts):
    rows, have_total = build_loss_funnel(funnel_counts)
    if not have_total: return '<div class="empty-note">Awaiting Data &mdash; pipeline has not reported an ingestion total.</div>'

    header = '<div class="loss-row head"><div>Evaluation Stage</div><div style="text-align:right;">Entering</div><div style="text-align:right;">Exiting</div><div style="text-align:right;">Terminations</div><div style="text-align:right;">Stage Conversion</div><div style="text-align:right;">% Dropped</div></div>'
    body = ""
    for r in rows:
        href = "archive.html" if r["stage_token"] is None else f'archive.html?stage={r["stage_token"]}'
        row_cls = "loss-row " + (r["kind"] if r["kind"] in ("terminal", "loss") else "")
        entering_html = esc(fmt_num(r["entering"])) if is_num(r["entering"]) else AWAITING_SPAN
        exiting_html = esc(fmt_num(r["exiting"])) if is_num(r["exiting"]) else AWAITING_SPAN
        lost_html = esc(fmt_num(r["lost"])) if is_num(r["lost"]) and r["kind"] != "start" else ('&mdash;' if r["kind"] == "start" else AWAITING_SPAN)
        
        reasons_html = ""
        if r.get("reasons"):
            reasons_html = '<div class="dr-breakdown">'
            for reason, count in r["reasons"].items():
                friendly_reason = reason.replace("dropped_", "").replace("_", " ").title()
                reasons_html += f'<div class="dr-item"><span>{friendly_reason}</span><span class="dr-count">{count}</span></div>'
            reasons_html += '</div>'
            
        body += f"""
            <a class="{row_cls}" href="{href}" title="Inspect this stage in the Decision Ledger">
                <div>
                    <div class="lr-name">{esc(r["label"])}</div>
                    {reasons_html}
                </div>
                <div class="lr-val">{entering_html}</div>
                <div class="lr-val">{exiting_html}</div>
                <div class="lr-val" style="color:var(--yellow); font-weight: bold;">{lost_html}</div>
                <div class="lr-val" style="color:var(--green); font-weight:700;">{fmt_pct(r["conv_pct"]) or "&mdash;"}</div>
                <div class="lr-val" style="color:var(--red);">{fmt_pct(r["loss_pct"]) or "&mdash;"}</div>
            </a>"""
    return f'<div class="loss-funnel">{header}{body}</div>'


BASE_CSS = """
        :root { --bg: #0a0e14; --surface: #11161d; --surface-subtle: #1a2029; --surface-hover: #222933; --border: #2a323d; --text: #c1c9d2; --muted: #79838f; --green: #2ea043; --red: #cb2431; --yellow: #dbab0a; --blue: #4088db; --mono: "SF Mono", "JetBrains Mono", Consolas, "Roboto Mono", monospace; }
        * { box-sizing: border-box; }
        body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; background-color: var(--bg); color: var(--text); margin: 0; padding: 12px; font-size: 13px; line-height: 1.4; }
        .container { max-width: 1800px; margin: 0 auto; }
        header { display: flex; justify-content: space-between; align-items: center; background: var(--surface); border: 1px solid var(--border); padding: 12px 18px; margin-bottom: 12px; border-left: 5px solid var(--green); }
        h1 { margin: 0; font-size: 1.3em; color: #fff; display: flex; align-items: center; gap: 10px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.5px; }
        .subline { color: var(--muted); margin-top: 4px; font-size: 0.85em; font-family: var(--mono); }
        .badge { padding: 2px 6px; border-radius: 3px; font-size: 0.7em; font-weight: 700; letter-spacing: 0.5px; }
        .badge.success { background: rgba(46,160,67,0.15); color: var(--green); border: 1px solid var(--green); }
        .badge.danger  { background: rgba(203,36,49,0.15); color: var(--red); border: 1px solid var(--red); }
        .badge.warn    { background: rgba(219,171,10,0.15); color: var(--yellow); border: 1px solid var(--yellow); }
        .badge.info    { background: rgba(64,136,219,0.15); color: var(--blue); border: 1px solid var(--blue); }
        .badge.awaiting{ background: rgba(121,131,143,0.12); color: var(--muted); border: 1px dashed var(--muted); }
        .nav-tabs { display: flex; gap: 8px; margin-bottom: 12px; flex-wrap: wrap;}
        .nav-tabs a { background: var(--surface); border: 1px solid var(--border); color: var(--text); padding: 7px 14px; text-decoration: none; font-weight: 600; font-size: 0.9em; text-transform: uppercase; letter-spacing: 0.5px; }
        .nav-tabs a.active { background: var(--blue); color: #fff; border-color: var(--blue); }
        .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(400px, 1fr)); gap: 12px; }
        .card { background: var(--surface); border: 1px solid var(--border); padding: 14px; }
        .card h2 { margin: 0 0 10px; font-size: 0.95em; color: #fff; text-transform: uppercase; letter-spacing: 0.8px; display: flex; justify-content: space-between; align-items: center; font-weight: 700; border-bottom: 1px solid var(--border); padding-bottom: 8px;}
        .tile-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(140px, 1fr)); gap: 8px; }
        .stat-tile { background: var(--surface-subtle); border: 1px solid var(--border); padding: 8px 10px; }
        .stat-label { font-size: 0.65em; text-transform: uppercase; color: var(--muted); letter-spacing: 0.5px; margin-bottom: 4px; font-weight: 600;}
        .stat-value { font-family: var(--mono); font-size: 1.15em; font-weight: 700; color: var(--text); }
        .awaiting { color: var(--muted); font-style: italic; font-size: 0.65em; font-weight: 600; letter-spacing: 0.3px; }
        table { width: 100%; border-collapse: collapse; font-size: 0.85em; }
        th, td { padding: 6px 8px; border-bottom: 1px solid var(--surface-subtle); text-align: left; vertical-align: top;}
        th { color: var(--muted); text-transform: uppercase; font-size: 0.7em; letter-spacing: 0.4px; cursor: pointer; user-select: none;}
        th:hover { color: #fff; background: var(--surface-hover); }
        .metric-val { text-align: right; font-family: var(--mono); }
        tr.clickable { cursor: pointer; } tr.clickable:hover { background: var(--surface-hover); }
        .loss-funnel { display: flex; flex-direction: column; }
        .loss-row { display: grid; grid-template-columns: 240px 1fr 1fr 1fr 1fr 1fr; gap: 8px; align-items: center; padding: 7px 4px; border-bottom: 1px solid var(--surface-subtle); text-decoration: none; color: var(--text); }
        .loss-row:hover { background: var(--surface-hover); }
        .loss-row .lr-name { font-weight: 600; font-size: 0.85em; }
        .loss-row .lr-val { font-family: var(--mono); text-align: right; font-size: 0.85em; }
        .loss-row.head { color: var(--muted); text-transform: uppercase; font-size: 0.65em; letter-spacing: 0.5px; border-bottom: 1px solid var(--border); padding-bottom: 6px; }
        .kpi-hero { display: flex; align-items: flex-start; gap: 24px; flex-wrap: wrap; }
        .kpi-number { font-family: var(--mono); font-size: 3em; font-weight: 800; color: #fff; line-height: 1; }
        .kpi-label { font-size: 0.75em; text-transform: uppercase; color: var(--muted); letter-spacing: 0.5px; margin-bottom: 6px; font-weight: 700;}
        .kpi-context-row { display: flex; gap: 20px; flex-wrap: wrap; margin-top: 12px; padding-top: 12px; border-top: 1px solid var(--border); width: 100%; }
        .kpi-context-item .cx-label { font-size: 0.65em; text-transform: uppercase; color: var(--muted); letter-spacing: 0.4px; }
        .kpi-context-item .cx-value { font-family: var(--mono); font-weight: 700; font-size: 1.05em; margin-top: 2px; }
        .empty-note { color: var(--muted); font-style: italic; padding: 8px 0; font-size: 0.85em; }
        .dr-breakdown { font-size: 0.75em; color: var(--muted); margin-top: 4px; }
        .dr-item { display: flex; justify-content: space-between; border-left: 2px solid var(--yellow); padding-left: 6px; margin-top: 2px; }
        .dr-count { font-family: var(--mono); color: var(--yellow); font-weight: bold;}
"""

NAV_TABS = """
            <div class="nav-tabs">
                <a href="index.html" class="{cls_index}">Operations Centre</a>
                <a href="pipeline_health.html" class="{cls_health}">Pipeline Health</a>
                <a href="decision_analytics.html" class="{cls_analytics}">Drift & Intelligence</a>
                <a href="archive.html" class="{cls_archive}">Daily Master Log</a>
            </div>"""

def render_nav(active):
    return NAV_TABS.format(
        cls_index="active" if active == "index" else "",
        cls_health="active" if active == "health" else "",
        cls_analytics="active" if active == "analytics" else "",
        cls_archive="active" if active == "archive" else ""
    )

SORT_JS = """
<script>
document.addEventListener('DOMContentLoaded', () => {
    document.querySelectorAll('th').forEach(th => th.addEventListener('click', (() => {
        const table = th.closest('table');
        Array.from(table.querySelectorAll('tr:nth-child(n+2)'))
            .sort(comparer(Array.from(th.parentNode.children).indexOf(th), this.asc = !this.asc))
            .forEach(tr => table.appendChild(tr) );
    })));
});
const getCellValue = (tr, idx) => tr.children[idx].innerText || tr.children[idx].textContent;
const comparer = (idx, asc) => (a, b) => ((v1, v2) => 
    v1 !== '' && v2 !== '' && !isNaN(v1.replace(/[,%]/g,'')) && !isNaN(v2.replace(/[,%]/g,'')) ? v1.replace(/[,%]/g,'') - v2.replace(/[,%]/g,'') : v1.toString().localeCompare(v2)
    )(getCellValue(asc ? a : b, idx), getCellValue(asc ? b : a, idx));
</script>
"""

def generate_dashboard_html(logs, output_path, metrics, avg_30=None, src_30=None):
    now_str = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    run_id = getattr(metrics, 'run_id', _daily(metrics, "run_id", 'SSR-OP-2026'))
    health_score = _daily(metrics, "health_score")

    if is_num(health_score) and health_score >= 90: health_label, health_border = "HEALTHY", "var(--green)"
    elif is_num(health_score) and health_score >= 70: health_label, health_border = "DEGRADED", "var(--yellow)"
    elif is_num(health_score): health_label, health_border = "DOWN", "var(--red)"
    else: health_label, health_border = "HEALTHY", "var(--green)"
    
    funnel_counts = _daily(metrics, "funnel", {})
    
    eng_downloaded = _get_stage_raw_count(funnel_counts, ["downloaded"]) or 0
    eng_duplicates = _get_stage_raw_count(funnel_counts, ["dropped_hash_duplicate", "duplicate"]) or 0
    eng_processed = eng_downloaded - eng_duplicates
    eng_ontology = _get_stage_raw_count(funnel_counts, ["dropped_ontology_score", "ontology"]) or 0
    eng_regex = _get_stage_raw_count(funnel_counts, ["dropped_rules_threshold", "rules"]) or 0
    eng_financial = _get_stage_raw_count(funnel_counts, ["dropped_untradeable_otc", "dropped_financial_t12", "dropped_insufficient_liquidity", "dropped_no_options_chain", "financial"]) or 0
    eng_alerts = _get_stage_raw_count(funnel_counts, ["alerts_generated"]) or 0
    
    eng_ai = _get_stage_raw_count(funnel_counts, ["dropped_entity_confidence", "dropped_entity_missing_ticker", "dropped_entity_unknown_issuer", "dropped_entity_missing_both", "ai_rejected_private", "dropped_ai_confidence", "ai_exhausted"]) or 0 
    
    eng_rss_down = _daily(metrics, "RSS_downloaded", 0)
    eng_html_down = _daily(metrics, "HTML_downloaded", 0)
    eng_rss_uniq = _daily(metrics, "RSS_unique", 0)
    eng_html_uniq = _daily(metrics, "HTML_unique", 0)
    eng_rss_alerts = _daily(metrics, "RSS_alerts", 0)
    eng_html_alerts = _daily(metrics, "HTML_alerts", 0)
    
    unique_arts = _daily(metrics, "unique_articles", eng_downloaded)
    global_dedupe = eng_downloaded - unique_arts if eng_downloaded > unique_arts else 0
    
    trust_row = "".join([
        f'<div class="stat-tile"><div class="stat-label">Articles Downloaded</div><div class="stat-value">{eng_downloaded}</div></div>',
        f'<div class="stat-tile"><div class="stat-label">Duplicates Removed</div><div class="stat-value">{eng_duplicates}</div></div>',
        f'<div class="stat-tile"><div class="stat-label">Articles Processed</div><div class="stat-value">{eng_processed}</div></div>',
        f'<div class="stat-tile"><div class="stat-label">Ontology Rejected</div><div class="stat-value">{eng_ontology}</div></div>',
        f'<div class="stat-tile"><div class="stat-label">Regex Rejected</div><div class="stat-value">{eng_regex}</div></div>',
        f'<div class="stat-tile"><div class="stat-label">Financial Rejected</div><div class="stat-value">{eng_financial}</div></div>',
        f'<div class="stat-tile"><div class="stat-label">Entity / AI Rejections</div><div class="stat-value">{eng_ai}</div></div>',
        f'<div class="stat-tile"><div class="stat-label">Alerts Generated</div><div class="stat-value" style="color:var(--green)">{eng_alerts}</div></div>'
    ])

    source_stats_raw = _daily(metrics, "source_stats", {})
    source_rows = []
    if source_stats_raw:
        for src, st in source_stats_raw.items():
            arts = st.get("downloaded", 0)
            alerts = st.get("alerts", 0)
            source_rows.append({
                "source": src,
                "articles": arts,
                "alerts": alerts,
                "alert_pct": round((alerts / arts * 100), 1) if arts else 0,
                "ontology_pct": round((st.get("survived_ontology", 0) / arts * 100), 1) if arts else 0,
                "rules_pct": round((st.get("survived_rules", 0) / arts * 100), 1) if arts else 0,
                "failures": st.get("failures", 0)
            })
    else:
        source_rows = [{"source": "Awaiting Sensor Integration", "articles": 0, "alerts": 0, "alert_pct": 0, "ontology_pct": 0, "rules_pct": 0, "failures": 0}]
    
    total_alerts_all_sources = sum(a for a in (_bag(r, "alerts") for r in source_rows) if is_num(a))
    source_row_html = "".join([
        f"""<tr>
            <td><strong>{esc(_bag(r, "source"))}</strong></td>
            <td class="metric-val">{esc(_bag(r, "articles"))}</td>
            <td class="metric-val">{esc(_bag(r, "alerts"))}</td>
            <td class="metric-val">{esc(fmt_pct(safe_div(_bag(r, "alerts"), total_alerts_all_sources) * 100 if total_alerts_all_sources else None)) or AWAITING_SPAN}</td>
            <td class="metric-val">{esc(_bag(r, "alert_pct"))}%</td>
            <td class="metric-val">{esc(_bag(r, "ontology_pct"))}%</td>
            <td class="metric-val">{esc(_bag(r, "rules_pct"))}%</td>
            <td class="metric-val" style="color: {'var(--red)' if _bag(r, 'failures', 0) else 'var(--text)'};">{esc(_bag(r, 'failures', 0))}</td>
            <td class="metric-val">{AWAITING_SPAN}</td>
            <td class="metric-val">{AWAITING_SPAN}</td>
            <td class="metric-val">{AWAITING_SPAN}</td>
        </tr>""" for r in source_rows
    ])

    ledger_rows_html = ""
    ingestion_ledger = metrics.get("ingestion_ledger", [])
    if ingestion_ledger:
        for row in sorted(ingestion_ledger, key=lambda x: (x.get("source", ""), x.get("channel", ""))):
            status = row.get("status", "UNKNOWN")
            if status == "OK" and row.get("parsed_found", 0) > 0:
                status_html = f'<span class="badge success">OK</span>'
                row_style = ""
            elif status == "EMPTY" or (status == "OK" and row.get("parsed_found", 0) == 0):
                status_html = f'<span class="badge warn">ZERO YIELD</span>'
                row_style = "color: var(--yellow);"
            else:
                status_html = f'<span class="badge danger">{esc(status)}</span>'
                row_style = "color: var(--red);"
                
            err = row.get("error_message", "")
            if err:
                err = f'<span style="font-size:0.85em; opacity:0.8;">{esc(err[:50])}</span>'
                
            ledger_rows_html += f"""<tr style="{row_style}">
                <td><strong>{esc(row.get('source'))}</strong></td>
                <td>{esc(row.get('channel'))}</td>
                <td><a href="{esc(row.get('url'))}" target="_blank" style="color: inherit; text-decoration: underline;">Link</a></td>
                <td class="metric-val">{esc(row.get('duration_sec'))}s</td>
                <td>{status_html}</td>
                <td class="metric-val">{esc(row.get('raw_found', 0))}</td>
                <td class="metric-val">{esc(row.get('parsed_found', 0))}</td>
                <td class="metric-val" style="font-weight:bold;">{esc(row.get('unique_found', 0))}</td>
                <td>{err}</td>
            </tr>"""
    else:
        ledger_rows_html = "<tr><td colspan='9' class='empty-note'>Awaiting next ingestion cycle to populate ledger.</td></tr>"

    html = f"""<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8"><title>SSR Operations Centre</title><style>{BASE_CSS}</style>{SORT_JS}</head>
    <body><div class="container">{render_nav("index")}
    <header style="border-left-color: {health_border};"><div><h1>Operations Centre</h1>
    <div class="subline">Manifest Configuration Hash: CFG-LATEST &bull; Re-Evaluated {esc(now_str)}</div></div></header>
    
    <div class="card" style="margin-bottom: 12px;"><h2>1. Engineering Metrics</h2><div class="tile-grid" style="grid-template-columns: repeat(auto-fill, minmax(160px, 1fr));">{trust_row}</div></div>
    
    <div class="card" style="margin-bottom: 12px; display: flex; gap: 20px;">
        <div style="flex: 1;">
            <h2>Acquisition Channels (RSS vs HTML)</h2>
            <div class="tile-grid" style="grid-template-columns: 1fr 1fr 1fr 1fr;">
                <div class="stat-tile" style="border:none; background:transparent;"><div class="stat-label">&nbsp;</div><div class="stat-value" style="font-size: 0.9em; color:var(--muted);">RSS</div><div class="stat-value" style="font-size: 0.9em; margin-top: 8px; color:var(--muted);">HTML</div></div>
                <div class="stat-tile"><div class="stat-label">Raw Downloaded</div><div class="stat-value" style="font-size: 0.9em;">{eng_rss_down}</div><div class="stat-value" style="font-size: 0.9em; margin-top: 8px;">{eng_html_down}</div></div>
                <div class="stat-tile"><div class="stat-label">Unique Yield</div><div class="stat-value" style="font-size: 0.9em;">{eng_rss_uniq}</div><div class="stat-value" style="font-size: 0.9em; margin-top: 8px;">{eng_html_uniq}</div></div>
                <div class="stat-tile"><div class="stat-label">Alerts Contributed</div><div class="stat-value" style="font-size: 0.9em; color:var(--green)">{eng_rss_alerts}</div><div class="stat-value" style="font-size: 0.9em; margin-top: 8px; color:var(--green)">{eng_html_alerts}</div></div>
            </div>
            <div style="margin-top: 10px; font-size: 0.85em; color: var(--yellow);">Global deduplication dropped <strong>{global_dedupe}</strong> overlapping cross-channel articles before processing.</div>
        </div>
    </div>
    
    <div class="card" style="margin-bottom: 12px; overflow-x: auto;"><h2>2. Sensor Feed Quality & Pipeline Yield</h2>
    <table><thead><tr><th>Sensor Identity</th><th>Articles Downloaded</th><th>Alerts Generated</th><th>Capture Share</th><th>Alert %</th><th>Ontology Yield %</th><th>Rules Yield %</th><th>Failures</th><th>Reliability</th><th>Avg Latency</th><th>Cost/Yield</th></tr></thead><tbody>{source_row_html}</tbody></table></div>
    
    <div class="card" style="margin-bottom: 12px; overflow-x: auto;"><h2>3. Source Acquisition Health & Ledger</h2>
    <div style="margin-bottom: 8px; font-size: 0.85em; color: var(--muted);">Real-time log of the most recent fetch cycle per channel. A <span style="color:var(--yellow)">ZERO YIELD</span> status indicates the channel successfully responded but provided no usable articles (often caused by navigation loops or static landing pages).</div>
    <table><thead><tr><th>Source</th><th>Channel</th><th>URL</th><th style="text-align:right;">Duration</th><th>Status</th><th style="text-align:right;">Raw Discovered</th><th style="text-align:right;">Parsed Successfully</th><th style="text-align:right;">Unique Yield</th><th>Error Context</th></tr></thead><tbody>{ledger_rows_html}</tbody></table></div>
    </div></body></html>"""
    
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f: f.write(html)


def generate_pipeline_health_html(output_path, metrics):
    now_str = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    funnel_counts = _daily(metrics, "funnel", {})
    loss_funnel_html = render_loss_funnel_html(funnel_counts)
    
    # Calculate total runtime, API calls, CPU time
    total_cpu_ms = 0.0
    total_net_ms = 0.0
    total_api = 0
    for stage, data in funnel_counts.items():
        if isinstance(data, dict):
            total_cpu_ms += data.get("cpu_ms", 0.0)
            total_net_ms += data.get("network_ms", 0.0)
            total_api += data.get("api_calls", 0)
            
    stats_row = "".join([
        f'<div class="stat-tile"><div class="stat-label">Total Execution Runtime</div><div class="stat-value">{metrics.get("runtime", 0.0)}s</div></div>',
        f'<div class="stat-tile"><div class="stat-label">Aggregate CPU Time</div><div class="stat-value">{round(total_cpu_ms, 2)}ms</div></div>',
        f'<div class="stat-tile"><div class="stat-label">Aggregate Network Latency</div><div class="stat-value">{round(total_net_ms, 2)}ms</div></div>',
        f'<div class="stat-tile"><div class="stat-label">External API Calls</div><div class="stat-value">{total_api}</div></div>'
    ])

    html = f"""<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8"><title>SSR Pipeline Health</title><style>{BASE_CSS}</style>{SORT_JS}</head>
    <body><div class="container">{render_nav("health")}
    <header><div><h1>Pipeline Health & Conversion</h1>
    <div class="subline">High-Resolution Pipeline Stage Diagnostics &bull; Re-Evaluated {esc(now_str)}</div></div></header>
    
    <div class="card" style="margin-bottom: 12px;">
        <h2>Pipeline Conversion Sankey / Funnel</h2>
        {loss_funnel_html}
    </div>
    
    <div class="card" style="margin-bottom: 12px;">
        <h2>Execution Telemetry Aggregates</h2>
        <div class="tile-grid">{stats_row}</div>
    </div>
    
    </div></body></html>"""
    
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f: f.write(html)


def generate_decision_analytics_html(output_path, metrics, avg_30=None):
    rule_data = _daily(metrics, "rule_analytics") or []
    ontology_data = _daily(metrics, "ontology_conversion") or []

    rule_rows_html = "".join([f"<tr><td>{esc(_bag(r, 'rule'))}</td><td class='metric-val'>{esc(_bag(r, 'evaluated'))}</td><td class='metric-val'>{esc(_bag(r, 'alerts'))}</td><td class='metric-val'>{AWAITING_SPAN}</td><td class='metric-val'>{AWAITING_SPAN}</td><td class='metric-val'>{AWAITING_SPAN}</td><td class='metric-val'>{AWAITING_SPAN}</td><td class='metric-val'>{AWAITING_SPAN}</td></tr>" for r in rule_data])
    if not rule_data: rule_rows_html = "<tr><td colspan='8' class='empty-note'>Awaiting Evidentiary DAG Replays</td></tr>"

    ontology_rows_html = "".join([f"<tr><td>{esc(_bag(o, 'concept'))}</td><td class='metric-val'>{esc(_bag(o, 'frequency'))}</td><td class='metric-val'>{AWAITING_SPAN}</td><td class='metric-val'>{AWAITING_SPAN}</td><td class='metric-val'>{AWAITING_SPAN}</td><td class='metric-val'>{AWAITING_SPAN}</td></tr>" for o in ontology_data])
    if not ontology_data: ontology_rows_html = "<tr><td colspan='6' class='empty-note'>Awaiting Evidentiary DAG Replays</td></tr>"
    
    html = f"""<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8"><title>SSR Concept Drift Analytics</title><style>{BASE_CSS}</style>{SORT_JS}</head>
    <body><div class="container">{render_nav("analytics")}<header><h1>Concept Drift & Rules Intelligence</h1></header>
    
    <div class="card" style="margin-bottom: 12px; overflow-x: auto;"><h2>Determinism Lineage: Rules Intelligence</h2>
    <table><thead><tr><th>Rule Component Version</th><th>Total Evaluated</th><th>Alerts Issued</th><th>Human Overrides</th><th>FP Contrib %</th><th>FN Contrib %</th><th>Capture Contrib</th><th>Avg DAG Weight</th></tr></thead><tbody>{rule_rows_html}</tbody></table></div>
    
    <div class="card" style="overflow-x: auto;"><h2>Ontology Lineage: Concept Drift Monitor</h2>
    <table><thead><tr><th>Taxonomy Concept Node</th><th>Observation Frequency</th><th>Drift Z-Score</th><th>FP Contrib</th><th>FN Contrib</th><th>Alert Conversion %</th></tr></thead><tbody>{ontology_rows_html}</tbody></table></div>
    </div></body></html>"""
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f: f.write(html)


def generate_ontology_debug_html(output_path):
    debug_css = """
        .table-wrapper { background: var(--surface); border: 1px solid var(--border); overflow-x: auto; }
        th { background: var(--surface-subtle); position: sticky; top: 0; z-index: 10; }
        .score-fail { color: var(--red); font-weight: bold; }
        .score-pass { color: var(--green); font-weight: bold; }
        .concept-tag { display: inline-block; background: var(--surface-subtle); border: 1px solid var(--border); padding: 2px 6px; margin: 2px; border-radius: 3px; font-size: 0.8em; }
        .concept-match { border-color: var(--green); color: var(--green); }
        .concept-miss { border-color: var(--border); color: var(--muted); }
    """
    html = """<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8"><title>SSR Ontology Debug</title><style>__BASE_CSS__ __DEBUG_CSS__</style>__SORT_JS__</head>
    <body><div class="container">__NAV__
        <header><h1>Ontology Debug</h1></header>
        
        <div class="card" style="margin-bottom:12px;">
            <h2>Concept Frequency Aggregation</h2>
            <div class="table-wrapper">
                <table id="conceptFreqTable">
                    <thead><tr><th>Concept ID</th><th>Match Count</th></tr></thead>
                    <tbody id="conceptFreqBody"></tbody>
                </table>
            </div>
        </div>

        <div class="card">
            <h2>Ontology Rejections (Score < 0.65)</h2>
            <div class="table-wrapper">
                <table id="ontologyTable">
                    <thead><tr><th>Headline</th><th>Source</th><th>Score</th><th>Threshold</th><th>Concepts Found</th><th>Missing Concepts</th></tr></thead>
                    <tbody id="tableBody"></tbody>
                </table>
            </div>
        </div>
    </div>
    
    <script>
        fetch('archive_data.json')
            .then(res => res.json())
            .then(data => {
                const ledger = Array.isArray(data) ? data : (data.ledger || []);
                const tbody = document.getElementById('tableBody');
                const freqBody = document.getElementById('conceptFreqBody');
                
                const freq = {};
                let html = '';
                
                ledger.forEach(item => {
                    const meta = item.ontology_metadata || {};
                    if(item.pipeline_stage === 'ontology_concepts') {
                        const score = meta.score || 0.0;
                        const matched = meta.matched || [];
                        const missing = meta.missing || [];
                        
                        matched.forEach(c => freq[c] = (freq[c] || 0) + 1);
                        
                        let matchHtml = matched.map(c => `<span class="concept-tag concept-match">${c}</span>`).join('');
                        let missHtml = missing.map(c => `<span class="concept-tag concept-miss">${c}</span>`).join('');
                        if(!matchHtml) matchHtml = '<span class="awaiting">None</span>';
                        
                        html += `<tr>
                            <td style="max-width:300px; white-space:normal;">${item.headline}</td>
                            <td>${item.syndication_lineage?.canonical_sensor_id || 'Unknown'}</td>
                            <td class="metric-val score-fail">${score.toFixed(2)}</td>
                            <td class="metric-val">0.65</td>
                            <td>${matchHtml}</td>
                            <td>${missHtml}</td>
                        </tr>`;
                    }
                });
                
                tbody.innerHTML = html || '<tr><td colspan="6" class="empty-note">No ontology rejections found in archive.</td></tr>';
                
                const sortedFreq = Object.entries(freq).sort((a,b) => b[1] - a[1]);
                let freqHtml = sortedFreq.map(([c, count]) => `<tr><td>${c}</td><td class="metric-val">${count}</td></tr>`).join('');
                freqBody.innerHTML = freqHtml || '<tr><td colspan="2" class="empty-note">No concepts matched.</td></tr>';
            });
    </script></body></html>"""
    
    html = html.replace("__BASE_CSS__", BASE_CSS).replace("__SORT_JS__", SORT_JS).replace("__DEBUG_CSS__", debug_css).replace("__NAV__", render_nav("debug"))
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f: f.write(html)

def generate_screening_log_html(output_path):
    screening_css = """
        .table-wrapper { background: var(--surface); border: 1px solid var(--border); overflow-x: auto; }
        th { background: var(--surface-subtle); position: sticky; top: 0; z-index: 10; }
        .filter-bar { display: flex; gap: 10px; flex-wrap: wrap; margin-bottom: 12px; align-items: center; }
        .filter-bar select, .filter-bar input { background: var(--surface); border: 1px solid var(--border); color: var(--text); padding: 6px 10px; font-size: 0.85em; font-family: inherit; }
        .filter-bar input { flex: 1; min-width: 200px; }
        .filter-bar label { font-size: 0.7em; text-transform: uppercase; color: var(--muted); letter-spacing: 0.4px; }
        .outcome-passed { color: var(--green); font-weight: 700; }
        .outcome-dropped { color: var(--red); font-weight: 700; }
        .reason-tag { font-family: var(--mono); color: var(--yellow); font-size: 0.85em; background: rgba(219,171,10,0.1); padding: 2px 6px; border-radius: 3px; }
        .headline-cell { max-width: 420px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
        .headline-cell a { color: var(--text); text-decoration: none; }
        .headline-cell a:hover { color: var(--blue); text-decoration: underline; }
        .result-count { color: var(--muted); font-size: 0.8em; margin-bottom: 8px; }
        .badge { display: inline-block; padding: 3px 6px; border-radius: 4px; font-size: 0.7em; font-weight: 600; text-transform: uppercase; background: var(--surface-subtle); border: 1px solid var(--border); margin-right: 4px; }
        .success { color: var(--green); border-color: rgba(66,211,146,0.3); }
        .warn { color: var(--yellow); border-color: rgba(219,171,10,0.3); }
        .mode-fallback { color: var(--yellow); font-weight: 700; font-size: 0.8em; }
        .mode-rss { color: var(--muted); font-size: 0.8em; }
        /* Modal Styles */
        .modal { display: none; position: fixed; z-index: 100; left: 0; top: 0; width: 100%; height: 100%; overflow: auto; background-color: rgba(0,0,0,0.8); }
        .modal-content { background-color: var(--surface); margin: 5% auto; padding: 20px; border: 1px solid var(--border); width: 80%; max-width: 900px; color: var(--text); border-radius: 6px; box-shadow: 0 4px 12px rgba(0,0,0,0.5); }
        .close { color: var(--muted); float: right; font-size: 28px; font-weight: bold; cursor: pointer; }
        .close:hover { color: #fff; }
        .modal-body { margin-top: 15px; white-space: pre-wrap; font-family: var(--mono); font-size: 0.9em; background: var(--bg); padding: 15px; border: 1px solid var(--border); border-radius: 4px; max-height: 60vh; overflow-y: auto;}
        .modal-title { font-size: 1.2em; font-weight: 600; margin-bottom: 10px; color: #fff;}
        .modal-meta { font-size: 0.8em; color: var(--muted); margin-bottom: 15px; }
    """

    html = """<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8"><title>Daily Master Log</title><style>__BASE_CSS__ __SCREENING_CSS__</style>__SORT_JS__</head>
    <body>
    
    <div id="articleModal" class="modal">
        <div class="modal-content">
            <span class="close" onclick="closeModal()">&times;</span>
            <div id="modalTitle" class="modal-title"></div>
            <div id="modalMeta" class="modal-meta"></div>
            <div id="modalBody" class="modal-body"></div>
        </div>
    </div>
    
    <div class="container">__NAV__<header><h1>Daily Master Log</h1></header>

    <div class="filter-bar">
        <div><label>Date</label><br><select id="dateFilter"></select></div>
        <div><label>News Source</label><br><select id="sourceFilter"><option value="">All Sources</option></select></div>
        <div><label>Drop Reason</label><br><select id="reasonFilter"><option value="">All Reasons</option></select></div>
        <div><label>Outcome</label><br><select id="outcomeFilter"><option value="">All</option><option value="PASSED">Passed</option><option value="DROPPED">Dropped</option></select></div>
        <div style="flex:1;"><label>Search (headline, source)</label><br><input type="text" id="searchBox" placeholder="Type to filter..."></div>
    </div>
    <div class="card" style="margin-bottom: 20px;">
        <h2>Real-Time Source Audit Metrics</h2>
        <div class="table-wrapper">
            <table id="auditTable">
                <thead>
                    <tr>
                        <th>Source</th>
                        <th>Mode</th>
                        <th>Grade</th>
                        <th>Status</th>
                        <th>Raw Found</th>
                        <th>30d Avg</th>
                        <th>Deviation %</th>
                        <th>Lifetime Rel %</th>
                        <th>Emergency Stop</th>
                    </tr>
                </thead>
                <tbody id="auditTableBody">
                    <tr><td colspan="9" style="text-align: center; color: var(--muted); padding: 20px;">Loading Source Audit...</td></tr>
                </tbody>
            </table>
        </div>
    </div>

    <div class="result-count" id="resultCount"></div>

    <div class="table-wrapper"><table id="screeningTable">
    <thead><tr><th>Timestamp (GMT)</th><th>Status</th><th>Company</th><th>Source</th><th>Headline (Click to Read)</th><th>Mode</th><th>Outcome</th><th>Final Stage</th><th>Drop Reason</th></tr></thead>
    <tbody id="tableBody"><tr><td colspan="9" style="text-align: center; color: var(--muted); padding: 30px;">Loading Master Log...</td></tr></tbody>
    </table></div></div>

    <script>
        fetch('realtime_audit.json')
            .then(res => res.json())
            .then(data => {
                const tbody = document.getElementById('auditTableBody');
                const metrics = data.source_metrics || [];
                if (metrics.length === 0) {
                    tbody.innerHTML = '<tr><td colspan="9" style="text-align:center; padding:20px;">No audit metrics available for today.</td></tr>';
                    return;
                }
                tbody.innerHTML = '';
                metrics.forEach(m => {
                    const tr = document.createElement('tr');
                    const emHtml = m.emergency_stop ? `<span class="badge danger">YES (${m.reason})</span>` : '<span class="badge success">NO</span>';
                    let gradeColor = 'inherit';
                    if (m.grade.startsWith('A')) gradeColor = 'var(--green)';
                    else if (m.grade === 'F') gradeColor = 'var(--red)';
                    else if (m.grade === 'D') gradeColor = 'var(--yellow)';
                    
                    tr.innerHTML = `
                        <td style="font-weight:bold;">${m.source}</td>
                        <td>${m.mode}</td>
                        <td style="color:${gradeColor}; font-weight:bold;">${m.grade}</td>
                        <td>${m.status_light}</td>
                        <td class="metric-val">${m.raw}</td>
                        <td class="metric-val">${m.avg_30d}</td>
                        <td class="metric-val" style="color:${m.dev_pct < -30 ? 'var(--red)' : (m.dev_pct > 30 ? 'var(--green)' : 'inherit')}">${m.dev_pct > 0 ? '+' : ''}${m.dev_pct}%</td>
                        <td class="metric-val">${m.lifetime_rel}%</td>
                        <td>${emHtml}</td>
                    `;
                    tbody.appendChild(tr);
                });
            })
            .catch(err => {
                console.error("Failed to load audit metrics:", err);
                document.getElementById('auditTableBody').innerHTML = '<tr><td colspan="9" style="text-align:center; color:var(--red);">Error loading audit metrics.</td></tr>';
            });
            
        let screeningData = [];
        let filteredData = [];
        let selectedDate = new Date().toISOString().split('T')[0];

        fetch('screening_log.json')
            .then(res => res.json())
            .then(data => {
                const allData = Array.isArray(data) ? data : (data.screening_log || []);
                window.allData = allData;
                
                // Populate Dates
                const dates = [...new Set(allData.map(r => r.timestamp ? r.timestamp.substring(0, 10) : null).filter(Boolean))].sort().reverse();
                const dateSel = document.getElementById('dateFilter');
                dates.forEach(d => {
                    const opt = document.createElement('option');
                    opt.value = d; opt.textContent = d;
                    dateSel.appendChild(opt);
                });
                
                if (dates.length > 0 && !dates.includes(selectedDate)) {
                    selectedDate = dates[0];
                } else if (dates.length === 0) {
                    selectedDate = '';
                }
                
                if (selectedDate) {
                    dateSel.value = selectedDate;
                }

                filterByDate();
            })
            .catch(err => {
                screeningData = [];
                renderTable();
            });

        function filterByDate() {
            selectedDate = document.getElementById('dateFilter').value;
            if (selectedDate) {
                screeningData = window.allData.filter(r => r.timestamp && r.timestamp.startsWith(selectedDate));
            } else {
                screeningData = window.allData;
            }
            populateFilters();
            renderTable();
        }

        function populateFilters() {
            const sourceSel = document.getElementById('sourceFilter');
            sourceSel.innerHTML = '<option value="">All Sources</option>';
            const sources = [...new Set(screeningData.map(r => r.source).filter(Boolean))].sort();
            sources.forEach(s => {
                const opt = document.createElement('option');
                opt.value = s; opt.textContent = s;
                sourceSel.appendChild(opt);
            });
            
            const reasonSel = document.getElementById('reasonFilter');
            reasonSel.innerHTML = '<option value="">All Reasons</option>';
            const reasons = [...new Set(screeningData.map(r => r.drop_reason).filter(Boolean))].sort();
            reasons.forEach(r => {
                const opt = document.createElement('option');
                opt.value = r; opt.textContent = r;
                reasonSel.appendChild(opt);
            });
        }

        document.getElementById('dateFilter').addEventListener('change', filterByDate);

        document.getElementById('sourceFilter').addEventListener('change', renderTable);
        document.getElementById('reasonFilter').addEventListener('change', renderTable);
        document.getElementById('outcomeFilter').addEventListener('change', renderTable);
        document.getElementById('searchBox').addEventListener('input', renderTable);

        function showModal(idx) {
            const r = filteredData[idx];
            if (!r) return;
            document.getElementById('modalTitle').textContent = r.headline || 'Untitled';
            document.getElementById('modalMeta').innerHTML = `<strong>Source:</strong> ${r.source || 'Unknown'} | <strong>Company:</strong> ${r.company_name || 'UNKNOWN'} | <a href="${r.url || '#'}" target="_blank" style="color:var(--blue)">Original Link</a>`;
            document.getElementById('modalBody').textContent = r.body_snippet || 'No article body available.';
            document.getElementById('articleModal').style.display = "block";
        }
        function closeModal() {
            document.getElementById('articleModal').style.display = "none";
        }
        window.onclick = function(event) {
            if (event.target == document.getElementById('articleModal')) {
                closeModal();
            }
        }

        function renderTable() {
            const tbody = document.getElementById('tableBody');
            const sourceVal = document.getElementById('sourceFilter').value;
            const reasonVal = document.getElementById('reasonFilter').value;
            const outcomeVal = document.getElementById('outcomeFilter').value;
            const searchVal = document.getElementById('searchBox').value.toLowerCase();

            filteredData = screeningData.filter(r => {
                if (sourceVal && r.source !== sourceVal) return false;
                if (reasonVal && r.drop_reason !== reasonVal) return false;
                if (outcomeVal && r.outcome !== outcomeVal) return false;
                if (searchVal) {
                    const hay = `${r.headline||''} ${r.source||''}`.toLowerCase();
                    if (!hay.includes(searchVal)) return false;
                }
                return true;
            });

            document.getElementById('resultCount').textContent = `Showing ${filteredData.length} of ${screeningData.length} articles for today (${todayGMT})`;

            tbody.innerHTML = '';
            if (filteredData.length === 0) {
                tbody.innerHTML = '<tr><td colspan="9" style="text-align:center; padding:20px;">No articles match the current filters.</td></tr>';
                return;
            }

            filteredData.forEach((r, idx) => {
                const tr = document.createElement('tr');
                const outcomeCls = r.outcome === 'PASSED' ? 'outcome-passed' : 'outcome-dropped';
                const reasonHtml = r.drop_reason ? `<span class="reason-tag">${r.drop_reason}</span>` : '';
                const modeCls = r.ingestion_mode === 'HTML_FALLBACK' ? 'mode-fallback' : 'mode-rss';
                const modeLabel = r.ingestion_mode === 'HTML_FALLBACK' ? 'FALLBACK' : (r.ingestion_mode || 'RSS');
                
                const statusHtml = r.drop_reason === 'dropped_hash_duplicate' 
                    ? '<span class="badge warn">DUPLICATE</span>' 
                    : '<span class="badge success">BRAND NEW</span>';
                
                tr.innerHTML = `<td>${r.timestamp || ''}</td>
                                <td>${statusHtml}</td>
                                <td style="font-weight:bold; color:var(--blue);">${r.company_name || 'UNKNOWN'}</td>
                                <td>${r.source || 'Unknown'}</td>
                                <td class="headline-cell"><a href="javascript:void(0)" onclick="showModal(${idx})" title="${(r.headline||'').replace(/"/g,'&quot;')}">${r.headline || 'Untitled'}</a></td>
                                <td class="${modeCls}">${modeLabel}</td>
                                <td class="${outcomeCls}">${r.outcome || ''}</td>
                                <td>${r.final_stage || ''}</td>
                                <td>${reasonHtml}</td>`;
                tbody.appendChild(tr);
            });
        }
    </script></body></html>"""

    html = html.replace("__BASE_CSS__", BASE_CSS).replace("__SORT_JS__", SORT_JS).replace("__SCREENING_CSS__", screening_css).replace("__NAV__", render_nav("archive"))
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f: f.write(html)

# Alias for backward compatibility with monitor.py callers
generate_screening_html = generate_screening_log_html