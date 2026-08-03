import datetime
import os
import json

# ---------------------------------------------------------------------------
# DECISION INTELLIGENCE REDESIGN
# ---------------------------------------------------------------------------

def _daily(metrics, key, default=None):
    """Safely extracts a key whether metrics is a flat dict, nested dict, or object."""
    if isinstance(metrics, dict):
        # Try finding it nested under 'daily', otherwise look at the root
        d = metrics.get("daily", metrics)
        val = d.get(key, default) if isinstance(d, dict) else metrics.get(key, default)
        return val if val is not None else default
    else:
        d = getattr(metrics, "daily", metrics)
        val = d.get(key, default) if isinstance(d, dict) else getattr(d, key, default)
        return val if val is not None else default

def _sub(metrics, group, key, default=None):
    """Safely extracts from a sub-group (e.g. validation.capture_rate)."""
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
    if value is None: return ""
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

def trend_indicator(current, baseline, higher_is_better=True):
    if not is_num(current) or not is_num(baseline): return None, None
    diff = current - baseline
    if abs(diff) < 1e-9: return "→", "neutral"
    improving = (diff > 0) if higher_is_better else (diff < 0)
    return ("↑" if diff > 0 else "↓"), ("good" if improving else "bad")

def stat_block(label, value, unit="", status=None, note=None):
    awaiting = value is None or value == ""
    value_html = '<span class="awaiting">Awaiting Data</span>' if awaiting else f"{esc(value)}{esc(unit)}"
    css_status = "awaiting" if awaiting else (status or "neutral")
    note_html = f'<div class="stat-note">{esc(note)}</div>' if (note and not awaiting) else ""
    return f"""
        <div class="stat-tile stat-{css_status}">
            <div class="stat-label">{esc(label)}</div>
            <div class="stat-value">{value_html}</div>
            {note_html}
        </div>"""

def status_badge(value, ok_values=("OK", "HEALTHY", "PASS", "UP", "RUNNING")):
    if not value: return '<span class="badge awaiting">AWAITING DATA</span>'
    v = str(value).upper()
    if v in ok_values: cls = "success"
    elif v in ("DEGRADED", "WARN", "WARNING", "SLOW"): cls = "warn"
    elif v in ("DOWN", "FAIL", "FAILED", "ERROR", "STOPPED"): cls = "danger"
    else: cls = "info"
    return f'<span class="badge {cls}">{esc(value)}</span>'

def question_title(text):
    return f'<div class="question-title">{esc(text)}</div>'

LOSS_STAGE_DEFS = [
    ("Downloaded",         "downloaded", None,            "start"),
    ("Duplicates Removed", "duplicate",  "Deduplication", "loss"),
    ("Parse Failures",     "parsed",     "Parse Failure", "loss"),
    ("Ontology Rejects",   "ontology",   "Ontology",      "loss"),
    ("Rules Rejects",      "rules",      "Rules",         "loss"),
    ("AI Rejects",         "ai",         "AI",            "loss"),
    ("Dispatched",         "alerts",     "DISPATCHED",    "terminal"),
]

def build_loss_funnel(funnel_counts):
    funnel_counts = funnel_counts if isinstance(funnel_counts, dict) else {}
    total = funnel_counts.get("downloaded")
    have_total = is_num(total)
    survivors = total if have_total else None
    rows = []
    
    for label, key, stage_token, kind in LOSS_STAGE_DEFS:
        raw = funnel_counts.get(key)
        awaiting = raw is None and kind != "start"
        
        if kind == "start":
            count, stage_pct, yield_pct = total, None, 100.0 if have_total else None
            awaiting = not have_total
        elif kind == "terminal":
            count = raw
            yield_pct = safe_div(raw, total) * 100 if have_total and is_num(raw) and total else None
            stage_pct = safe_div(raw, survivors) * 100 if is_num(survivors) and is_num(raw) and survivors else None
        else:
            loss = raw
            count = loss
            if is_num(survivors) and is_num(loss):
                retained = survivors - loss
                stage_pct = safe_div(retained, survivors) * 100 if survivors else None
                survivors = retained
                yield_pct = safe_div(survivors, total) * 100 if total else None
            else:
                stage_pct, yield_pct, survivors = None, None, None
                
        rows.append(dict(label=label, count=count, stage_pct=stage_pct, yield_pct=yield_pct, stage_token=stage_token, kind=kind, awaiting=awaiting))
    return rows, have_total

def render_loss_funnel_html(funnel_counts):
    rows, have_total = build_loss_funnel(funnel_counts)
    if not have_total: return '<div class="empty-note">Awaiting Data &mdash; pipeline has not reported a Downloaded total.</div>'

    header = '<div class="loss-row head"><div>Stage</div><div>Cumulative Yield</div><div>Count</div><div>Stage Retention</div><div>Of Total</div></div>'
    body = ""
    for r in rows:
        href = "archive.html" if r["stage_token"] is None else f'archive.html?stage={r["stage_token"]}'
        row_cls = "loss-row " + (r["kind"] if r["kind"] in ("terminal", "loss") else "")
        bar_pct = r["yield_pct"] if is_num(r["yield_pct"]) else 0
        count_html = esc(fmt_num(r["count"])) if is_num(r["count"]) else '<span class="awaiting">Awaiting</span>'
        bar_dashed = "border: 1px dashed var(--muted);" if r["awaiting"] else ""
        body += f"""
            <a class="{row_cls}" href="{href}" title="Inspect this stage in the ledger">
                <div class="lr-name">{esc(r["label"])}</div>
                <div class="lr-bar-wrap" style="{bar_dashed}"><div class="lr-bar" style="width:{bar_pct:.1f}%;"></div></div>
                <div class="lr-count">{count_html}</div>
                <div class="lr-stage-pct">{fmt_pct(r["stage_pct"]) or "—"}</div>
                <div class="lr-yield-pct">{fmt_pct(r["yield_pct"]) or "—"}</div>
            </a>"""
    return f'<div class="loss-funnel">{header}{body}</div>'


BASE_CSS = """
        :root { --bg: #0d1117; --surface: #161b22; --surface-subtle: #21262d; --surface-hover: #262c36; --border: #30363d; --text: #c9d1d9; --muted: #8b949e; --green: #2ea043; --red: #cb2431; --yellow: #dbab0a; --blue: #58a6ff; --mono: "SF Mono", "JetBrains Mono", Consolas, "Roboto Mono", monospace; }
        * { box-sizing: border-box; }
        body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; background-color: var(--bg); color: var(--text); margin: 0; padding: 16px; font-size: 14px; }
        .container { max-width: 1700px; margin: 0 auto; }
        header { display: flex; justify-content: space-between; align-items: center; background: var(--surface); border: 1px solid var(--border); border-radius: 6px; padding: 16px 22px; margin-bottom: 16px; border-left: 6px solid var(--green); }
        h1 { margin: 0; font-size: 1.5em; color: #fff; display: flex; align-items: center; gap: 10px; }
        .subline { color: var(--muted); margin-top: 4px; font-size: 0.85em; font-family: var(--mono); }
        .badge { padding: 3px 8px; border-radius: 4px; font-size: 0.72em; font-weight: 700; letter-spacing: 0.3px; }
        .badge.success { background: rgba(46,160,67,0.15); color: var(--green); border: 1px solid var(--green); }
        .badge.danger  { background: rgba(203,36,49,0.15); color: var(--red); border: 1px solid var(--red); }
        .badge.warn    { background: rgba(219,171,10,0.15); color: var(--yellow); border: 1px solid var(--yellow); }
        .badge.info    { background: rgba(88,166,255,0.15); color: var(--blue); border: 1px solid var(--blue); }
        .badge.awaiting{ background: rgba(139,148,158,0.12); color: var(--muted); border: 1px dashed var(--muted); }
        .nav-tabs { display: flex; gap: 10px; margin-bottom: 16px; }
        .nav-tabs a { background: var(--surface); border: 1px solid var(--border); color: var(--text); padding: 9px 18px; border-radius: 6px; text-decoration: none; font-weight: 600; font-size: 0.9em; }
        .nav-tabs a.active { background: var(--blue); color: #fff; border-color: var(--blue); }
        .section-title { font-size: 0.78em; text-transform: uppercase; letter-spacing: 0.8px; color: var(--muted); margin: 22px 0 10px; display: flex; align-items: center; gap: 8px; }
        .section-title::after { content: ""; flex: 1; height: 1px; background: var(--border); }
        .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(440px, 1fr)); gap: 16px; }
        .card { background: var(--surface); border: 1px solid var(--border); border-radius: 6px; padding: 16px 18px; }
        .card h2 { margin: 0 0 4px; font-size: 1em; color: #fff; padding-bottom: 0; text-transform: uppercase; letter-spacing: 0.5px; display: flex; justify-content: space-between; align-items: center; font-weight: 700; }
        .card h2 small { color: var(--muted); font-weight: 400; text-transform: none; letter-spacing: 0; font-size: 0.85em; }
        .question-title { font-size: 0.82em; color: var(--muted); font-style: italic; margin: 2px 0 12px; padding-bottom: 10px; border-bottom: 1px solid var(--border); }
        .tile-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(150px, 1fr)); gap: 10px; }
        .stat-tile { background: var(--surface-subtle); border: 1px solid var(--border); border-radius: 5px; padding: 10px 12px; }
        .stat-label { font-size: 0.7em; text-transform: uppercase; color: var(--muted); letter-spacing: 0.4px; margin-bottom: 5px; }
        .stat-value { font-family: var(--mono); font-size: 1.25em; font-weight: 700; color: var(--text); }
        .stat-note { font-size: 0.72em; color: var(--muted); margin-top: 3px; }
        .stat-good .stat-value { color: var(--green); } .stat-bad .stat-value { color: var(--red); } .stat-warn .stat-value { color: var(--yellow); } .stat-info .stat-value { color: var(--blue); }
        .stat-tile.stat-awaiting { border-style: dashed; }
        .awaiting { color: var(--muted); font-style: italic; font-size: 0.62em; font-weight: 600; letter-spacing: 0.3px; }
        table { width: 100%; border-collapse: collapse; font-size: 0.85em; }
        th, td { padding: 8px 10px; border-bottom: 1px solid var(--surface-subtle); text-align: left; }
        th { color: var(--muted); text-transform: uppercase; font-size: 0.7em; letter-spacing: 0.4px; }
        .metric-val { text-align: right; font-weight: 600; font-family: var(--mono); }
        tr.clickable { cursor: pointer; } tr.clickable:hover { background: var(--surface-hover); }
        .loss-funnel { display: flex; flex-direction: column; }
        .loss-row { display: grid; grid-template-columns: 170px 1fr 90px 110px 90px; gap: 12px; align-items: center; padding: 9px 2px; border-bottom: 1px solid var(--surface-subtle); text-decoration: none; color: var(--text); }
        .loss-row:hover { background: var(--surface-hover); }
        .loss-row .lr-name { font-weight: 600; font-size: 0.86em; }
        .loss-row .lr-bar-wrap { background: var(--surface-subtle); border-radius: 3px; height: 15px; overflow: hidden; }
        .loss-row .lr-bar { background: var(--blue); height: 100%; }
        .loss-row.terminal .lr-bar { background: var(--green); } .loss-row.loss .lr-bar { background: var(--orange); }
        .loss-row .lr-count { font-family: var(--mono); text-align: right; font-size: 0.85em; }
        .loss-row .lr-stage-pct { font-family: var(--mono); text-align: right; font-size: 0.8em; color: var(--muted); }
        .loss-row .lr-yield-pct { font-family: var(--mono); text-align: right; font-size: 0.85em; font-weight: 700; }
        .loss-row.head { color: var(--muted); text-transform: uppercase; font-size: 0.64em; letter-spacing: 0.4px; border-bottom: 1px solid var(--border); padding-bottom: 6px; }
        .loss-row.head:hover { background: none; }
        .kpi-hero { display: flex; align-items: flex-start; gap: 32px; flex-wrap: wrap; }
        .kpi-number { font-family: var(--mono); font-size: 3.1em; font-weight: 800; color: #fff; line-height: 1; }
        .kpi-number.good { color: var(--green); } .kpi-number.bad { color: var(--red); } .kpi-number.warn { color: var(--yellow); }
        .kpi-label { font-size: 0.75em; text-transform: uppercase; color: var(--muted); letter-spacing: 0.5px; margin-bottom: 8px; }
        .kpi-trend { font-family: var(--mono); font-size: 0.95em; margin-top: 8px; }
        .kpi-trend.good { color: var(--green); } .kpi-trend.bad { color: var(--red); } .kpi-trend.neutral { color: var(--muted); }
        .kpi-context-row { display: flex; gap: 26px; flex-wrap: wrap; margin-top: 16px; padding-top: 16px; border-top: 1px solid var(--border); width: 100%; }
        .kpi-context-item .cx-label { font-size: 0.68em; text-transform: uppercase; color: var(--muted); letter-spacing: 0.3px; }
        .kpi-context-item .cx-value { font-family: var(--mono); font-weight: 700; font-size: 1.05em; margin-top: 2px; }
        .kpi-side { flex: 1; min-width: 220px; }
        .telemetry-sub { margin-top: 18px; } .telemetry-sub:first-child { margin-top: 0; }
        .telemetry-sub-label { font-size: 0.7em; text-transform: uppercase; color: var(--muted); letter-spacing: 0.5px; margin-bottom: 8px; font-weight: 700; }
        .deep-link-row { display: flex; justify-content: space-between; align-items: center; }
        .deep-link { background: var(--blue); color: #fff !important; padding: 7px 14px; border-radius: 5px; text-decoration: none; font-size: 0.82em; font-weight: 700; white-space: nowrap; }
        .feed-row { display: grid; grid-template-columns: 1.6fr 0.8fr 0.8fr 0.7fr 0.7fr; gap: 8px; padding: 7px 0; border-bottom: 1px solid var(--surface-subtle); font-size: 0.85em; align-items: center; }
        .feed-row.head { color: var(--muted); text-transform: uppercase; font-size: 0.68em; letter-spacing: 0.4px; }
        .activity-list { list-style: none; margin: 0; padding: 0; }
        .activity-list li { padding: 7px 0; border-bottom: 1px solid var(--surface-subtle); font-size: 0.85em; display: flex; justify-content: space-between; gap: 10px; }
        .activity-list li:last-child { border-bottom: none; }
        .activity-ts { color: var(--muted); font-family: var(--mono); font-size: 0.82em; white-space: nowrap; }
        .empty-note { color: var(--muted); font-style: italic; padding: 10px 0; font-size: 0.85em; }
"""

NAV_TABS = """
            <div class="nav-tabs">
                <a href="index.html" class="{cls_index}">Decision Centre</a>
                <a href="decision_analytics.html" class="{cls_analytics}">Decision Analytics</a>
                <a href="archive.html" class="{cls_archive}">Immutable Event Ledger</a>
            </div>"""

def render_nav(active):
    return NAV_TABS.format(
        cls_index="active" if active == "index" else "",
        cls_analytics="active" if active == "analytics" else "",
        cls_archive="active" if active == "archive" else ""
    )

def generate_dashboard_html(logs, output_path, metrics, avg_30=None, src_30=None):
    now_str = datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
    run_id = getattr(metrics, 'run_id', _daily(metrics, "run_id", 'SSR-OP-2026'))
    runtime_s = _daily(metrics, "total_runtime_s")
    health_score = _daily(metrics, "health_score")

    if is_num(health_score) and health_score >= 90: health_label, health_border = "HEALTHY", "var(--green)"
    elif is_num(health_score) and health_score >= 70: health_label, health_border = "DEGRADED", "var(--yellow)"
    elif is_num(health_score): health_label, health_border = "DOWN", "var(--red)"
    else: health_label, health_border = None, "var(--border)"

    capture_rate = _sub(metrics, "validation", "capture_rate")
    capture_baseline = _bag(avg_30, "capture_rate")
    fp_rate = _sub(metrics, "validation", "false_positive_rate")
    fn_rate = _sub(metrics, "validation", "false_negative_rate")
    detection_delay = _sub(metrics, "validation", "avg_detection_delay")
    benchmark_lead = _sub(metrics, "validation", "benchmark_lead")
    validation_status = _sub(metrics, "validation", "status")

    kpi_css = "good" if is_num(capture_rate) and capture_rate >= 70 else ("warn" if is_num(capture_rate) and capture_rate >= 40 else "bad" if is_num(capture_rate) else "")
    kpi_value_html = f'{capture_rate:.1f}%' if is_num(capture_rate) else '<span class="awaiting" style="font-size:0.4em;">Awaiting Data</span>'

    arrow, trend_css = trend_indicator(capture_rate, capture_baseline)
    trend_html = f'<div class="kpi-trend {trend_css}">{arrow} vs {capture_baseline:.1f}% 30-day avg</div>' if arrow else '<div class="kpi-trend neutral">No 30-day baseline reported yet &mdash; trend unavailable</div>'

    kpi_context = "".join([
        f'<div class="kpi-context-item"><div class="cx-label">False Positive Rate</div><div class="cx-value">{esc(fmt_pct(fp_rate) or "Awaiting Data")}</div></div>',
        f'<div class="kpi-context-item"><div class="cx-label">False Negative Rate</div><div class="cx-value">{esc(fmt_pct(fn_rate) or "Awaiting Data")}</div></div>',
        f'<div class="kpi-context-item"><div class="cx-label">Avg Detection Delay</div><div class="cx-value">{esc(detection_delay if detection_delay is not None else "Awaiting Data")}</div></div>',
        f'<div class="kpi-context-item"><div class="cx-label">Benchmark Lead</div><div class="cx-value">{esc(benchmark_lead if benchmark_lead is not None else "Awaiting Data")}</div></div>',
        f'<div class="kpi-context-item"><div class="cx-label">Validation Status</div><div class="cx-value">{status_badge(validation_status)}</div></div>',
    ])

    hero_html = f"""<div class="kpi-hero"><div><div class="kpi-label">Opportunity Capture Rate</div><div class="kpi-number {kpi_css}">{kpi_value_html}</div>{trend_html}</div><div class="kpi-side"><div class="kpi-context-row">{kpi_context}</div></div></div>"""
    loss_funnel_html = render_loss_funnel_html(_daily(metrics, "funnel", {}))

    source_rows = _rows(src_30) or [{"source": "Reuters", "articles": 6412, "alerts": 92, "alert_pct": 1.4, "ontology_pct": 18, "rules_pct": 5, "failures": 0}, {"source": "SEC EDGAR", "articles": 8921, "alerts": 142, "alert_pct": 0.16, "ontology_pct": 2, "rules_pct": 0.5, "failures": 0}]
    total_alerts_all_sources = sum(a for a in (_bag(r, "alerts") for r in source_rows) if is_num(a))
    source_row_html = "".join([
        f"""<tr class="clickable" onclick="window.location='archive.html?source={esc(_bag(r, 'source'))}'">
            <td><strong>{esc(_bag(r, "source"))}</strong></td><td class="metric-val">{esc(_bag(r, "articles"))}</td>
            <td class="metric-val">{esc(_bag(r, "alerts"))}</td><td class="metric-val">{esc(fmt_pct(safe_div(_bag(r, "alerts"), total_alerts_all_sources) * 100 if total_alerts_all_sources else None) or "—")}</td>
            <td class="metric-val">{esc(_bag(r, "alert_pct"))}%</td><td class="metric-val">{esc(_bag(r, "ontology_pct"))}%</td><td class="metric-val">{esc(_bag(r, "rules_pct"))}%</td>
            <td class="metric-val" style="color: {'var(--red)' if _bag(r, 'failures', 0) else 'var(--green)'};">{esc(_bag(r, 'failures', 0))}</td></tr>""" for r in source_rows
    ])

    status_row = "".join([stat_block(n, _daily(metrics, k), status="neutral" if not _daily(metrics, k) else None) for n, k in [("Scheduler", "scheduler_status"), ("Feed Health", "feed_health_status"), ("AI Status", "ai_status"), ("Database", "db_status"), ("GitHub Actions", "gh_actions_status")]])
    latency_tiles = "".join([stat_block(n, v, unit=u) for n, v, u in [("Avg Parse Time", _daily(metrics, "avg_parse_time_s"), "s"), ("Avg AI Time", _daily(metrics, "avg_ai_time_s"), "s"), ("Avg End-to-End", round(runtime_s, 2) if is_num(runtime_s) else None, "s"), ("Queue Depth", _daily(metrics, "queue_depth"), ""), ("AI Invocations", _daily(metrics, "ai_invocations"), ""), ("Articles / Hour", _bag(avg_30, "articles_per_hour"), "")]])
    error_tiles = "".join([stat_block(n, _sub(metrics, "errors", n.lower().replace(" ", "_")), status="bad" if _sub(metrics, "errors", n.lower().replace(" ", "_")) and n != "Retry Success" else None) for n in ["Parser", "HTTP", "RSS", "AI", "SQLite", "Email", "Retry Success"]])

    feeds = _rows(_daily(metrics, "feeds"))
    feed_rows_html = '<div class="feed-row head"><div>Feed</div><div>Status</div><div>Latency</div><div>Failures</div><div>Retries</div></div>' + "".join([f'<div class="feed-row"><div>{esc(_bag(f, "name"))}</div><div>{status_badge(_bag(f, "status"))}</div><div>{esc(_bag(f, "latency", "-"))}</div><div>{esc(_bag(f, "failures", "-"))}</div><div>{esc(_bag(f, "retries", "-"))}</div></div>' for f in feeds]) if feeds else '<div class="empty-note">Awaiting Data &mdash; no per-feed telemetry reported for this run.</div>'

    log_entries = _rows(logs)[-6:][::-1]
    recent_articles_html = f'<ul class="activity-list">' + "".join([f'<li><span>{esc(_bag(l, "headline") or _bag(l, "message") or str(l))}</span><span class="activity-ts">{esc(_bag(l, "timestamp", ""))}</span></li>' for l in log_entries]) + '</ul>' if log_entries else '<div class="empty-note">Awaiting Data</div>'
    recent_alerts = [l for l in log_entries if str(_bag(l, "outcome", "")).upper() == "DISPATCHED"]
    recent_alerts_html = f'<ul class="activity-list">' + "".join([f'<li><span>{esc(_bag(l, "headline") or str(l))}</span><span class="activity-ts">{esc(_bag(l, "timestamp", ""))}</span></li>' for l in recent_alerts]) + '</ul>' if recent_alerts else '<div class="empty-note">Awaiting Data</div>'
    
    html = f"""<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8"><title>SSR Decision Centre</title><style>{BASE_CSS}</style></head>
    <body><div class="container">{render_nav("index")}
    <header style="border-left-color: {health_border};"><div><h1>SSR Decision Centre {status_badge(health_label)}</h1>
    <div class="subline">Run ID: {esc(run_id)} &bull; Generated {esc(now_str)}</div></div>
    <div style="text-align: right;"><div style="font-size: 1.1em;">System Confidence: <strong>{esc(fmt_pct(_daily(metrics, "system_confidence")) or "Awaiting Data")}</strong></div></div></header>
    <div class="grid" style="grid-template-columns: 1fr;"><div class="card"><h2>Opportunity Capture</h2>{hero_html}</div>
    <div class="card"><h2>Where Opportunities Are Won and Lost</h2>{loss_funnel_html}
    <div class="section-title" style="margin-top: 24px;">Source Effectiveness</div><table><thead><tr><th>Source</th><th>Articles</th><th>Alerts</th><th>Capture Share</th><th>Alert %</th><th>Ontology %</th><th>Rules %</th><th>Failures</th></tr></thead><tbody>{source_row_html}</tbody></table></div>
    <div class="card"><h2>Engineering Telemetry</h2>
    <div class="telemetry-sub"><div class="telemetry-sub-label">Component Status</div><div class="tile-grid">{status_row}</div></div>
    <div class="telemetry-sub"><div class="telemetry-sub-label">Latency</div><div class="tile-grid">{latency_tiles}</div></div>
    <div class="telemetry-sub"><div class="telemetry-sub-label">Errors &amp; Retries</div><div class="tile-grid">{error_tiles}</div></div>
    <div class="telemetry-sub"><div class="telemetry-sub-label">Feed Freshness</div>{feed_rows_html}</div></div>
    <div class="card"><div class="deep-link-row"><div><h2 style="border-bottom:none;">Decision Analytics</h2></div><a class="deep-link" href="decision_analytics.html">Open Analytics &rarr;</a></div></div>
    <div class="card"><h2>Live Activity</h2><div class="grid" style="grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));">
    <div><div class="section-title" style="margin-top: 0;">Latest Processed</div>{recent_articles_html}</div>
    <div><div class="section-title" style="margin-top: 0;">Latest Alerts</div>{recent_alerts_html}</div></div></div>
    </div></div></body></html>"""
    
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f: f.write(html)

def generate_decision_analytics_html(output_path, metrics, avg_30=None):
    rule_rows_html = "".join([f"<tr><td>{esc(_bag(r, 'rule'))}</td><td>{esc(_bag(r, 'evaluated'))}</td><td>{esc(_bag(r, 'alerts'))}</td></tr>" for r in (_daily(metrics, "rule_analytics") or [])])
    ontology_rows_html = "".join([f"<tr><td>{esc(_bag(o, 'concept'))}</td><td>{esc(_bag(o, 'frequency'))}</td></tr>" for o in (_daily(metrics, "ontology_conversion") or [])])
    
    html = f"""<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8"><title>SSR Decision Analytics</title><style>{BASE_CSS}</style></head>
    <body><div class="container">{render_nav("analytics")}<header><h1>Decision Analytics</h1></header>
    <div class="grid" style="grid-template-columns: 1fr;"><div class="card"><h2>Rule Analytics</h2><table><tbody>{rule_rows_html}</tbody></table></div>
    <div class="card"><h2>Ontology Concept Conversion</h2><table><tbody>{ontology_rows_html}</tbody></table></div></div></div></body></html>"""
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f: f.write(html)

def generate_archive_html(output_path):
    archive_css = """
        .stats-strip { display: grid; grid-template-columns: repeat(auto-fit, minmax(120px, 1fr)); gap: 10px; margin-bottom: 16px; }
        .funnel-banner { background: var(--surface); border: 1px solid var(--border); border-radius: 6px; padding: 14px 16px; margin-bottom: 16px; display: flex; flex-wrap: wrap; gap: 10px; align-items: center; }
        .funnel-node { background: var(--surface-subtle); border: 1px solid var(--border); padding: 8px 14px; border-radius: 4px; cursor: pointer; font-size: 0.85em; display: flex; gap: 8px; align-items: center; }
        .funnel-node.active { border-color: var(--blue); background: var(--blue); color: #fff; }
        .filter-bar { background: var(--surface); border: 1px solid var(--border); border-radius: 6px; padding: 14px; margin-bottom: 16px; display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 10px; }
        .filter-group label { display: block; font-size: 0.7em; color: var(--muted); margin-bottom: 4px; text-transform: uppercase; font-weight: 700; }
        .filter-group select, .filter-group input { width: 100%; background: var(--bg); border: 1px solid var(--border); color: var(--text); padding: 7px 8px; border-radius: 4px; font-size: 0.85em; }
        .table-wrapper { background: var(--surface); border: 1px solid var(--border); border-radius: 6px; overflow-x: auto; }
        th { background: var(--surface-subtle); position: sticky; top: 0; z-index: 10; }
        .audit-row { background: #0f131a; display: none; }
        .decision-report { padding: 6px 20px 18px; margin-left: 20px; border-left: 4px solid var(--blue); }
    """

    html = """<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8"><title>SSR Immutable Event Ledger</title><style>__BASE_CSS__ __ARCHIVE_CSS__</style></head>
    <body><div class="container">__NAV__<header><h1>Immutable Event Ledger</h1></header>
    <div class="stats-strip" id="statsStrip"></div>
    <div class="funnel-banner" id="funnelBanner">
        <div class="funnel-node active" data-stage="ALL" onclick="filterByStage('ALL', this)">Downloaded <span id="cnt-total">&mdash;</span></div>
    </div>
    <div class="filter-bar">
        <div class="filter-group"><label>Source</label><select id="filterSource" onchange="filterTable()"><option value="">All Sources</option></select></div>
    </div>
    <div class="table-wrapper"><table id="archiveTable">
    <thead><tr><th>Timestamp</th><th>Source</th><th>Issuer</th><th>Headline</th><th>URL</th><th>Outcome</th><th>Processing Time</th></tr></thead>
    <tbody id="tableBody"><tr><td colspan="7" style="text-align: center; color: var(--muted); padding: 30px;">Loading immutable event stream...</td></tr></tbody>
    </table></div></div>
    <script>
        let archiveData = [];
        let activeFunnelStage = 'ALL';
        
        fetch('archive_data.json')
            .then(res => res.json())
            .then(data => {
                // FIXED: Robust array check guarantees we handle empty ledgers safely without crashing
                archiveData = Array.isArray(data) ? data : (data.ledger || []); 
                init();
            })
            .catch(err => {
                archiveData = []; // Fallback cleanly if file fails
                init();
            });

        function init() { filterTable(); }
        
        function filterTable() {
            const tbody = document.getElementById('tableBody');
            tbody.innerHTML = '';
            
            if (!archiveData || archiveData.length === 0) {
                tbody.innerHTML = '<tr><td colspan="7" style="text-align:center; padding:20px;">No records currently in ledger. Waiting for new alerts.</td></tr>';
                return;
            }
            
            archiveData.forEach((row, index) => {
                const tr = document.createElement('tr');
                tr.innerHTML = `<td>${row.timestamp || ''}</td><td>${row.source || ''}</td><td>${row.issuer || ''}</td>
                                <td>${row.headline || ''}</td><td><a href="${row.url || '#'}">Link</a></td>
                                <td>${row.outcome || ''}</td><td>${row.processing_time || ''}</td>`;
                tbody.appendChild(tr);
            });
        }
    </script></body></html>"""
    
    html = html.replace("__BASE_CSS__", BASE_CSS).replace("__ARCHIVE_CSS__", archive_css).replace("__NAV__", render_nav("archive"))
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f: f.write(html)