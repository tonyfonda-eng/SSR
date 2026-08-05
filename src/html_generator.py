import datetime
import os
import json

# ---------------------------------------------------------------------------
# SSR 2.0 INSTITUTIONAL OPERATIONS CENTRE & DECISION INTELLIGENCE
# Consumes Canonical Decision Manifests & Operational Telemetry
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

# Updated to reflect SSR 2.0 Evaluation Stages
LOSS_STAGE_DEFS = [
    ("Sensor Ingestion",      "downloaded",          None,                     "start"),
    ("Idempotency & Dedupe",  "duplicate",           "Ingestion",              "loss"),
    ("Global Exclusions",     "exclusion",           "Global Exclusions",      "loss"),
    ("Ontology Extraction",   "ontology",            "Ontology",               "loss"),
    ("Deterministic Rules",   "rules",               "Rules Engine",           "loss"),
    ("AI Entity Resolution",  "ai_rejected_private", "AI Core",                "loss"),
    ("AI Strategy Playbook",  "ai",                  "AI Classification",      "loss"),
    ("Financial Verification","financial",           "Financial Verification", "loss"),
    ("Detected & Dispatched", "alerts",              "Complete",               "terminal"),
]

def build_loss_funnel(funnel_counts):
    funnel_counts = funnel_counts if isinstance(funnel_counts, dict) else {}
    total = funnel_counts.get("downloaded")
    have_total = is_num(total)
    entering = total if have_total else None
    rows = []
    
    for label, key, stage_token, kind in LOSS_STAGE_DEFS:
        raw = funnel_counts.get(key)
        awaiting = raw is None and kind != "start"
        
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
            lost = raw
            if is_num(entering) and is_num(lost):
                exiting = entering - lost
                loss_pct = safe_div(lost, entering) * 100 if entering else None
                conv_pct = safe_div(exiting, entering) * 100 if entering else None
            else:
                exiting, conv_pct, loss_pct = None, None, None
                
        rows.append(dict(label=label, entering=entering, exiting=exiting, lost=lost, conv_pct=conv_pct, loss_pct=loss_pct, stage_token=stage_token, kind=kind, awaiting=awaiting))
        
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
        lost_html = esc(fmt_num(r["lost"])) if is_num(r["lost"]) and r["kind"] != "start" else ('â€”' if r["kind"] == "start" else AWAITING_SPAN)
        
        body += f"""
            <a class="{row_cls}" href="{href}" title="Inspect this stage in the Decision Ledger">
                <div class="lr-name">{esc(r["label"])}</div>
                <div class="lr-val">{entering_html}</div>
                <div class="lr-val">{exiting_html}</div>
                <div class="lr-val" style="color:var(--yellow);">{lost_html}</div>
                <div class="lr-val" style="color:var(--green); font-weight:700;">{fmt_pct(r["conv_pct"]) or "â€”"}</div>
                <div class="lr-val" style="color:var(--red);">{fmt_pct(r["loss_pct"]) or "â€”"}</div>
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
        .nav-tabs { display: flex; gap: 8px; margin-bottom: 12px; }
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
        .loss-row { display: grid; grid-template-columns: 180px 1fr 1fr 1fr 1fr 1fr; gap: 8px; align-items: center; padding: 7px 4px; border-bottom: 1px solid var(--surface-subtle); text-decoration: none; color: var(--text); }
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
        .activity-list { list-style: none; margin: 0; padding: 0; }
        .activity-list li { padding: 6px 0; border-bottom: 1px solid var(--surface-subtle); font-size: 0.85em; display: flex; justify-content: space-between; gap: 10px; }
        .activity-list li:last-child { border-bottom: none; }
        .activity-ts { color: var(--muted); font-family: var(--mono); font-size: 0.82em; white-space: nowrap; }
"""

NAV_TABS = """
            <div class="nav-tabs">
                <a href="index.html" class="{cls_index}">Operations Centre</a>
                <a href="decision_analytics.html" class="{cls_analytics}">Drift & Intelligence</a>
                <a href="archive.html" class="{cls_archive}">Decision Ledger Manifests</a>
                <a href="screening_log.html" class="{cls_screening}">Article Screening Log</a>
            </div>"""

def render_nav(active):
    return NAV_TABS.format(
        cls_index="active" if active == "index" else "",
        cls_analytics="active" if active == "analytics" else "",
        cls_archive="active" if active == "archive" else "",
        cls_screening="active" if active == "screening" else ""
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
    else: health_label, health_border = None, "var(--border)"

    # Section 1: Trust & Operational Status
    trust_row = "".join([
        f'<div class="stat-tile"><div class="stat-label">Overall Health</div><div class="stat-value">{status_badge(health_label)}</div></div>',
        f'<div class="stat-tile"><div class="stat-label">Validation Status</div><div class="stat-value">{status_badge(_sub(metrics, "validation", "status"))}</div></div>',
        f'<div class="stat-tile"><div class="stat-label">Research Fidelity (CI)</div><div class="stat-value">{esc(fmt_pct(_daily(metrics, "system_confidence"))) or AWAITING_SPAN}</div></div>',
        f'<div class="stat-tile"><div class="stat-label">Last Successful Run</div><div class="stat-value">{esc(now_str)}</div></div>',
        f'<div class="stat-tile"><div class="stat-label">Sensor Asset Health</div><div class="stat-value">{status_badge(_daily(metrics, "feed_health_status", "OK"))}</div></div>',
        f'<div class="stat-tile"><div class="stat-label">AI Strategy Engine</div><div class="stat-value">{status_badge(_daily(metrics, "ai_status", "OK"))}</div></div>',
        f'<div class="stat-tile"><div class="stat-label">Evidence Repository</div><div class="stat-value">{status_badge(_daily(metrics, "db_status", "OK"))}</div></div>'
    ])

    # Section 2: Opportunity Capture
    capture_rate = _sub(metrics, "validation", "capture_rate")
    fp_rate = _sub(metrics, "validation", "false_positive_rate")
    fn_rate = _sub(metrics, "validation", "false_negative_rate")
    detection_delay = _sub(metrics, "validation", "avg_detection_delay")

    kpi_value_html = f'{capture_rate:.1f}%' if is_num(capture_rate) else f'<span class="awaiting" style="font-size:0.4em;">AWAITING CONTINUOUS VALIDATION</span>'
    kpi_context = "".join([
        f'<div class="kpi-context-item"><div class="cx-label">False Positive Rate</div><div class="cx-value">{esc(fmt_pct(fp_rate)) or AWAITING_SPAN}</div></div>',
        f'<div class="kpi-context-item"><div class="cx-label">False Negative (Miss) Rate</div><div class="cx-value">{esc(fmt_pct(fn_rate)) or AWAITING_SPAN}</div></div>',
        f'<div class="kpi-context-item"><div class="cx-label">Avg Detection Delay</div><div class="cx-value">{esc(detection_delay) if detection_delay is not None else AWAITING_SPAN}</div></div>',
    ])
    hero_html = f"""<div class="kpi-hero"><div><div class="kpi-label">Opportunity Capture Rate (vs Golden Dataset)</div><div class="kpi-number">{kpi_value_html}</div></div><div style="flex:1; min-width:220px;"><div class="kpi-context-row">{kpi_context}</div></div></div>"""

    # Section 3: Pipeline Loss Analysis
    loss_funnel_html = render_loss_funnel_html(_daily(metrics, "funnel", {}))

    # Section 4: Sensor Intelligence
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

    html = f"""<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8"><title>SSR Operations Centre</title><style>{BASE_CSS}</style>{SORT_JS}</head>
    <body><div class="container">{render_nav("index")}
    <header style="border-left-color: {health_border};"><div><h1>Operations Centre</h1>
    <div class="subline">Manifest Configuration Hash: CFG-LATEST &bull; Re-Evaluated {esc(now_str)}</div></div></header>
    
    <div class="card" style="margin-bottom: 12px;"><h2>1. Validation & Platform Status</h2><div class="tile-grid" style="grid-template-columns: repeat(auto-fill, minmax(160px, 1fr));">{trust_row}</div></div>
    
    <div class="card" style="margin-bottom: 12px;"><h2>2. Continuous Alpha Validation</h2>{hero_html}</div>
    
    <div class="card" style="margin-bottom: 12px;"><h2>3. Evaluation Funnel Metrics</h2>{loss_funnel_html}</div>
    
    <div class="card" style="margin-bottom: 12px; overflow-x: auto;"><h2>4. Sensor Asset Intelligence (SPI)</h2>
    <table><thead><tr><th>Sensor Identity</th><th>Artifacts Ingested</th><th>Decisions</th><th>Capture Share</th><th>Alert %</th><th>Ontology %</th><th>Rules %</th><th>Failures</th><th>Reliability</th><th>Avg Latency</th><th>Cost/Yield</th></tr></thead><tbody>{source_row_html}</tbody></table></div>
    </div></body></html>"""
    
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f: f.write(html)


def generate_decision_analytics_html(output_path, metrics, avg_30=None):
    rule_data = _daily(metrics, "rule_analytics") or []
    ontology_data = _daily(metrics, "ontology_conversion") or []

    # Section 5: Rule Intelligence
    rule_rows_html = "".join([f"<tr><td>{esc(_bag(r, 'rule'))}</td><td class='metric-val'>{esc(_bag(r, 'evaluated'))}</td><td class='metric-val'>{esc(_bag(r, 'alerts'))}</td><td class='metric-val'>{AWAITING_SPAN}</td><td class='metric-val'>{AWAITING_SPAN}</td><td class='metric-val'>{AWAITING_SPAN}</td><td class='metric-val'>{AWAITING_SPAN}</td><td class='metric-val'>{AWAITING_SPAN}</td></tr>" for r in rule_data])
    if not rule_data: rule_rows_html = "<tr><td colspan='8' class='empty-note'>Awaiting Evidentiary DAG Replays</td></tr>"

    # Section 6: Ontology Intelligence
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


def generate_archive_html(output_path):
    archive_css = """
        .table-wrapper { background: var(--surface); border: 1px solid var(--border); overflow-x: auto; }
        th { background: var(--surface-subtle); position: sticky; top: 0; z-index: 10; }
        .decision-report-row { display: none; background: #0f131a; }
        .decision-report-row.expanded { display: table-row; }
        .decision-report { padding: 16px 24px; border-left: 4px solid var(--blue); display: grid; grid-template-columns: repeat(auto-fit, minmax(320px, 1fr)); gap: 20px;}
        .drop-reason { font-family: var(--mono); color: var(--yellow); font-size: 0.9em; background: rgba(219,171,10,0.1); padding: 2px 6px; border-radius: 3px;}
        .dr-block h4 { margin: 0 0 8px; font-size: 0.8em; text-transform: uppercase; color: var(--muted); letter-spacing: 0.5px; border-bottom: 1px solid var(--border); padding-bottom: 4px;}
        .dr-list { list-style: none; margin: 0; padding: 0; font-size: 0.85em; }
        .dr-list li { margin-bottom: 6px; display: flex; justify-content: space-between; gap: 12px; }
        .dr-list li strong { color: var(--text); font-weight: normal; white-space: nowrap;}
        .dr-list li span { font-family: var(--mono); color: #fff; text-align: right; }
        .replay-btn { background: var(--surface-subtle); color: var(--text); border: 1px solid var(--border); padding: 6px 12px; cursor: pointer; border-radius: 4px; font-weight: 600; text-transform: uppercase; font-size: 0.75em; letter-spacing: 0.5px; width: 100%; margin-top: 10px;}
        .replay-btn:hover { background: var(--blue); color: #fff; border-color: var(--blue); }
        .evidence-for { border-left: 3px solid var(--green); padding-left: 8px; margin-bottom: 8px;}
        .evidence-against { border-left: 3px solid var(--red); padding-left: 8px; margin-bottom: 8px;}
    """

    html = """<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8"><title>SSR Canonical Decision Manifests</title><style>__BASE_CSS__ __ARCHIVE_CSS__</style>__SORT_JS__</head>
    <body><div class="container">__NAV__<header><h1>Canonical Decision Manifests</h1></header>
    
    <div class="table-wrapper"><table id="archiveTable">
    <thead><tr><th>Execution Timestamp (GMT)</th><th>Canonical Sensor</th><th>Entity / Target</th><th>Final Outcome</th><th>Terminal Stage</th><th>Confidence Score</th></tr></thead>
    <tbody id="tableBody"><tr><td colspan="6" style="text-align: center; color: var(--muted); padding: 30px;">Mounting Canonical Decision Manifest API...</td></tr></tbody>
    </table></div></div>
    
    <script>
        let archiveData = [];
        
        fetch('archive_data.json')
            .then(res => res.json())
            .then(data => {
                archiveData = Array.isArray(data) ? data : (data.ledger || []); 
                init();
            })
            .catch(err => {
                archiveData = []; 
                init();
            });

        function init() { renderTable(); }
        
        function toggleRow(idx) {
            const el = document.getElementById('detail-' + idx);
            if (el) el.classList.toggle('expanded');
        }
        
        function renderTable() {
            const tbody = document.getElementById('tableBody');
            tbody.innerHTML = '';
            
            if (!archiveData || archiveData.length === 0) {
                tbody.innerHTML = '<tr><td colspan="6" style="text-align:center; padding:20px;">No decision manifests exposed in API.</td></tr>';
                return;
            }
            
            archiveData.forEach((manifest, index) => {
                // Parse SSR 2.0 Canonical Structure with Legacy Fallbacks
                const reg = manifest.manifest_registry || {};
                const det = manifest.detection_vector || {};
                const prov = manifest.evidentiary_provenance_dag || {supporting_evidence: [], opposing_evidence: []};
                const perf = manifest.performance_telemetry_ms || {};
                const line = manifest.syndication_lineage || {};
                
                let ts = reg.execution_timestamp_gmt || manifest.timestamp || '';
                let outcome = det.outcome || manifest.outcome || 'PENDING';
                let stage = det.terminal_stage || manifest.pipeline_stage || 'Unknown';
                let sensor = line.canonical_sensor_id || manifest.source || 'Unknown Sensor';
                let ticker = det.target_ticker || manifest.issuer || 'UNKNOWN';
                
                let confDecomp = det.confidence_decomposition || {};
                let aggConf = confDecomp.aggregate_confidence || manifest.confidence || 0.0;
                let confStr = aggConf > 0 ? (aggConf * 100).toFixed(1) + '%' : '<span class="awaiting">N/A</span>';
                
                // Main Row
                const tr = document.createElement('tr');
                tr.className = 'clickable';
                tr.onclick = () => toggleRow(index);
                tr.innerHTML = `<td>${ts}</td>
                                <td><strong>${sensor}</strong></td>
                                <td>${ticker}</td>
                                <td><strong>${outcome}</strong></td>
                                <td>${stage}</td>
                                <td class="metric-val">${confStr}</td>`;
                
                // Build Supporting Evidence HTML
                let suppHtml = prov.supporting_evidence.map(e => `
                    <div class="evidence-for">
                        <div style="font-size:0.8em; color:var(--muted); text-transform:uppercase;">${e.component || e.stage} (Wt: ${e.weight || e.confidence_weight || 1.0})</div>
                        <div>${e.assertion || e.assertion_key}</div>
                    </div>`).join('');
                if(!suppHtml) suppHtml = '<div class="empty-note">No supporting causal links recorded.</div>';

                // Build Opposing Evidence HTML
                let oppHtml = prov.opposing_evidence.map(e => `
                    <div class="evidence-against">
                        <div style="font-size:0.8em; color:var(--muted); text-transform:uppercase;">${e.component || e.stage} (Wt: ${e.weight || e.confidence_weight || 1.0})</div>
                        <div>${e.assertion || e.assertion_key}</div>
                    </div>`).join('');
                // Legacy support for single "drop reason" mapped to opposing evidence
                if(!oppHtml && manifest.reason) {
                    oppHtml = `<div class="evidence-against"><div>Legacy Termination: ${manifest.reason}</div></div>`;
                }
                if(!oppHtml) oppHtml = '<div class="empty-note">No opposing causal links recorded.</div>';

                // Expanded Manifest Report Row
                const dTr = document.createElement('tr');
                dTr.id = 'detail-' + index;
                dTr.className = 'decision-report-row';
                dTr.innerHTML = `
                    <td colspan="6" style="padding: 0;">
                        <div class="decision-report">
                            <div class="dr-block">
                                <h4>Manifest Identifiers & Lineage</h4>
                                <ul class="dr-list">
                                    <li><strong>Decision ID:</strong> <span>${reg.decision_id || 'Legacy-Data'}</span></li>
                                    <li><strong>Core Event ID:</strong> <span>${reg.event_id || 'Legacy-Data'}</span></li>
                                    <li><strong>Config Manifest:</strong> <span>${reg.configuration_manifest_hash || 'SSR-CFG-LEGACY'}</span></li>
                                    <li><strong>Completeness Score:</strong> <span>${reg.evidence_completeness_score ? (reg.evidence_completeness_score*100).toFixed(0)+'%' : '100%'}</span></li>
                                </ul>
                                <h4 style="margin-top:16px;">Execution Timings (ms)</h4>
                                <ul class="dr-list">
                                    <li><strong>Repo Ingest:</strong> <span>${perf.ingest_repo_ms || perf.download || 0}</span></li>
                                    <li><strong>Text Transforms:</strong> <span>${perf.transformation_ms || perf.transformation || 0}</span></li>
                                    <li><strong>Ontology Engine:</strong> <span>${perf.ontology_ms || perf.ontology || 0}</span></li>
                                    <li><strong>Rules Engine:</strong> <span>${perf.rules_ms || perf.rules || 0}</span></li>
                                    <li><strong>AI Inference:</strong> <span>${perf.ai_inference_ms || perf.ai || 0}</span></li>
                                </ul>
                            </div>
                            <div class="dr-block">
                                <h4>Supporting Causal DAG</h4>
                                ${suppHtml}
                            </div>
                            <div class="dr-block">
                                <h4>Opposing / Terminal Causal DAG</h4>
                                ${oppHtml}
                            </div>
                            <div class="dr-block">
                                <h4>Strategy Decoupling & Human Audit</h4>
                                <ul class="dr-list">
                                    <li><strong>Human Override:</strong> <span><span class="awaiting">None</span></span></li>
                                    <li><strong>Strategy Validation:</strong> <span><span class="awaiting">Pending Sync</span></span></li>
                                    <li><strong>Market Cap Floor:</strong> <span><span class="awaiting">Unavailable</span></span></li>
                                    <li><strong>Options Verification:</strong> <span><span class="awaiting">Unavailable</span></span></li>
                                </ul>
                                <button class="replay-btn" onclick="alert('Immutable Replay triggered for Event ID: ${reg.event_id || 'Unknown'} via Configuration Manifest ${reg.configuration_manifest_hash || 'Latest'}.')">Trigger Deterministic Replay</button>
                            </div>
                        </div>
                    </td>
                `;
                
                tbody.appendChild(tr);
                tbody.appendChild(dTr);
            });
        }
    </script></body></html>"""
    
    html = html.replace("__BASE_CSS__", BASE_CSS).replace("__SORT_JS__", SORT_JS).replace("__ARCHIVE_CSS__", archive_css).replace("__NAV__", render_nav("archive"))
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
    """

    html = """<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8"><title>SSR Article Screening Log</title><style>__BASE_CSS__ __SCREENING_CSS__</style>__SORT_JS__</head>
    <body><div class="container">__NAV__<header><h1>Article Screening Log</h1></header>

    <div class="filter-bar">
        <div><label>Outcome</label><br><select id="outcomeFilter"><option value="">All</option><option value="PASSED">Passed</option><option value="DROPPED">Dropped</option></select></div>
        <div><label>Stage</label><br><select id="stageFilter"><option value="">All Stages</option></select></div>
        <div style="flex:1;"><label>Search (headline, ticker, source)</label><br><input type="text" id="searchBox" placeholder="Type to filter..."></div>
    </div>
    <div class="result-count" id="resultCount"></div>

    <div class="table-wrapper"><table id="screeningTable">
    <thead><tr><th>Timestamp (GMT)</th><th>Source</th><th>Headline</th><th>Ticker</th><th>Outcome</th><th>Final Stage</th><th>Drop Reason</th></tr></thead>
    <tbody id="tableBody"><tr><td colspan="7" style="text-align: center; color: var(--muted); padding: 30px;">Loading Screening Log...</td></tr></tbody>
    </table></div></div>

    <script>
        let screeningData = [];

        fetch('screening_log.json')
            .then(res => res.json())
            .then(data => {
                screeningData = Array.isArray(data) ? data : (data.screening_log || []);
                populateStageFilter();
                renderTable();
            })
            .catch(err => {
                screeningData = [];
                renderTable();
            });

        function populateStageFilter() {
            const stages = [...new Set(screeningData.map(r => r.final_stage).filter(Boolean))].sort();
            const sel = document.getElementById('stageFilter');
            stages.forEach(s => {
                const opt = document.createElement('option');
                opt.value = s; opt.textContent = s;
                sel.appendChild(opt);
            });
        }

        document.getElementById('outcomeFilter').addEventListener('change', renderTable);
        document.getElementById('stageFilter').addEventListener('change', renderTable);
        document.getElementById('searchBox').addEventListener('input', renderTable);

        function renderTable() {
            const tbody = document.getElementById('tableBody');
            const outcomeVal = document.getElementById('outcomeFilter').value;
            const stageVal = document.getElementById('stageFilter').value;
            const searchVal = document.getElementById('searchBox').value.toLowerCase();

            let filtered = screeningData.filter(r => {
                if (outcomeVal && r.outcome !== outcomeVal) return false;
                if (stageVal && r.final_stage !== stageVal) return false;
                if (searchVal) {
                    const hay = `${r.headline||''} ${r.ticker||''} ${r.source||''}`.toLowerCase();
                    if (!hay.includes(searchVal)) return false;
                }
                return true;
            });

            document.getElementById('resultCount').textContent = `Showing ${filtered.length} of ${screeningData.length} screened articles`;

            tbody.innerHTML = '';
            if (filtered.length === 0) {
                tbody.innerHTML = '<tr><td colspan="7" style="text-align:center; padding:20px;">No screened articles match the current filters.</td></tr>';
                return;
            }

            filtered.forEach(r => {
                const tr = document.createElement('tr');
                const outcomeCls = r.outcome === 'PASSED' ? 'outcome-passed' : 'outcome-dropped';
                const reasonHtml = r.drop_reason ? `<span class="reason-tag">${r.drop_reason}</span>` : '';
                tr.innerHTML = `<td>${r.timestamp || ''}</td>
                                <td>${r.source || 'Unknown'}</td>
                                <td class="headline-cell"><a href="${r.url || '#'}" target="_blank" title="${(r.headline||'').replace(/"/g,'&quot;')}">${r.headline || 'Untitled'}</a></td>
                                <td>${r.ticker || 'UNKNOWN'}</td>
                                <td class="${outcomeCls}">${r.outcome || ''}</td>
                                <td>${r.final_stage || ''}</td>
                                <td>${reasonHtml}</td>`;
                tbody.appendChild(tr);
            });
        }
    </script></body></html>"""

    html = html.replace("__BASE_CSS__", BASE_CSS).replace("__SORT_JS__", SORT_JS).replace("__SCREENING_CSS__", screening_css).replace("__NAV__", render_nav("screening"))
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f: f.write(html)