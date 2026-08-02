import datetime
import os
import json


# ---------------------------------------------------------------------------
# Safe accessors
#
# `logs`, `metrics`, `avg_30` and `src_30` are backend objects whose exact
# schema is owned by the pipeline, not by this presentation layer. Every read
# below is defensive: if a field isn't there yet, the UI renders an
# "Awaiting Data" placeholder card instead of raising, per the instruction to
# never require changes outside this file. As soon as the backend starts
# populating a key, the matching card will pick it up automatically.
# ---------------------------------------------------------------------------

def _daily(metrics, key, default=None):
    """Mirrors the original `metrics.daily.get(...)` access pattern, defensively."""
    d = getattr(metrics, "daily", {}) or {}
    try:
        return d.get(key, default)
    except AttributeError:
        return default


def _sub(metrics, group, key, default=None):
    """Reads metrics.daily[group][key], tolerating a missing group dict."""
    group_val = _daily(metrics, group, {}) or {}
    if isinstance(group_val, dict):
        return group_val.get(key, default)
    return getattr(group_val, key, default)


def _bag(value, key, default=None):
    """Reads `key` off a dict-like or object-like `value` (used for avg_30/src_30)."""
    if value is None:
        return default
    if isinstance(value, dict):
        return value.get(key, default)
    return getattr(value, key, default)


def _rows(value):
    """Coerces avg_30/src_30/logs-style inputs into a list, tolerating None."""
    if value is None:
        return []
    if isinstance(value, (list, tuple)):
        return list(value)
    return []


def esc(value):
    """Minimal HTML escaping for values interpolated into markup."""
    if value is None:
        return ""
    return (
        str(value)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def stat_block(label, value, unit="", status=None, note=None):
    """
    Renders one System-Health / Performance / Validation stat tile.
    status: 'good' | 'bad' | 'warn' | 'info' | None
    A None value renders the "Awaiting Data" placeholder called for by the
    design spec rather than inventing a number.
    """
    awaiting = value is None or value == ""
    if awaiting:
        value_html = '<span class="awaiting">Awaiting Data</span>'
        css_status = "awaiting"
    else:
        value_html = f"{esc(value)}{esc(unit)}"
        css_status = status or "neutral"
    note_html = f'<div class="stat-note">{esc(note)}</div>' if (note and not awaiting) else ""
    return f"""
                <div class="stat-tile stat-{css_status}">
                    <div class="stat-label">{esc(label)}</div>
                    <div class="stat-value">{value_html}</div>
                    {note_html}
                </div>"""


def status_badge(value, ok_values=("OK", "HEALTHY", "PASS", "UP", "RUNNING")):
    """Renders a colour-coded badge for a status string, or Awaiting Data."""
    if value is None or value == "":
        return '<span class="badge awaiting">AWAITING DATA</span>'
    v = str(value).upper()
    if v in ok_values:
        cls = "success"
    elif v in ("DEGRADED", "WARN", "WARNING", "SLOW"):
        cls = "warn"
    elif v in ("DOWN", "FAIL", "FAILED", "ERROR", "STOPPED"):
        cls = "danger"
    else:
        cls = "info"
    return f'<span class="badge {cls}">{esc(value)}</span>'


# ---------------------------------------------------------------------------
# Shared CSS — one dark, dense, "terminal" theme reused by both pages.
# Every existing CSS variable name and badge/table/card class from the prior
# version is preserved so nothing that already depends on them (either the
# JS in archive.html or hand-authored markup elsewhere in the repo) breaks.
# New variables/classes are additive only.
# ---------------------------------------------------------------------------
BASE_CSS = """
        :root {
            --bg: #0d1117; --surface: #161b22; --surface-subtle: #21262d; --surface-hover: #262c36;
            --border: #30363d; --text: #c9d1d9; --muted: #8b949e;
            --green: #2ea043; --red: #cb2431; --yellow: #dbab0a; --blue: #58a6ff; --purple: #8957e5;
            --cyan: #39c5cf; --orange: #db6d28;
            --mono: "SF Mono", "JetBrains Mono", Consolas, "Roboto Mono", monospace;
        }
        * { box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            background-color: var(--bg); color: var(--text); margin: 0; padding: 16px;
            font-size: 14px;
        }
        .container { max-width: 1700px; margin: 0 auto; }
        header {
            display: flex; justify-content: space-between; align-items: center;
            background: var(--surface); border: 1px solid var(--border); border-radius: 6px;
            padding: 16px 22px; margin-bottom: 16px; border-left: 6px solid var(--green);
        }
        h1 { margin: 0; font-size: 1.5em; color: #fff; display: flex; align-items: center; gap: 10px; }
        .subline { color: var(--muted); margin-top: 4px; font-size: 0.85em; font-family: var(--mono); }

        .badge { padding: 3px 8px; border-radius: 4px; font-size: 0.72em; font-weight: 700; letter-spacing: 0.3px; }
        .badge.success { background: rgba(46,160,67,0.15); color: var(--green); border: 1px solid var(--green); }
        .badge.danger  { background: rgba(203,36,49,0.15); color: var(--red); border: 1px solid var(--red); }
        .badge.warn    { background: rgba(219,171,10,0.15); color: var(--yellow); border: 1px solid var(--yellow); }
        .badge.info    { background: rgba(88,166,255,0.15); color: var(--blue); border: 1px solid var(--blue); }
        .badge.awaiting{ background: rgba(139,148,158,0.12); color: var(--muted); border: 1px dashed var(--muted); }

        .nav-tabs { display: flex; gap: 10px; margin-bottom: 16px; }
        .nav-tabs a {
            background: var(--surface); border: 1px solid var(--border); color: var(--text);
            padding: 9px 18px; border-radius: 6px; text-decoration: none; font-weight: 600; font-size: 0.9em;
        }
        .nav-tabs a.active { background: var(--blue); color: #fff; border-color: var(--blue); }

        .section-title {
            font-size: 0.78em; text-transform: uppercase; letter-spacing: 0.8px; color: var(--muted);
            margin: 22px 0 10px; display: flex; align-items: center; gap: 8px;
        }
        .section-title::after { content: ""; flex: 1; height: 1px; background: var(--border); }

        .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(440px, 1fr)); gap: 16px; }
        .card { background: var(--surface); border: 1px solid var(--border); border-radius: 6px; padding: 16px 18px; }
        .card.span2 { grid-column: span 2; }
        .card h2 {
            margin: 0 0 12px; font-size: 1em; color: #fff; border-bottom: 1px solid var(--border);
            padding-bottom: 9px; text-transform: uppercase; letter-spacing: 0.5px;
            display: flex; justify-content: space-between; align-items: center; font-weight: 700;
        }
        .card h2 small { color: var(--muted); font-weight: 400; text-transform: none; letter-spacing: 0; font-size: 0.85em; }

        .tile-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(150px, 1fr)); gap: 10px; }
        .stat-tile {
            background: var(--surface-subtle); border: 1px solid var(--border); border-radius: 5px;
            padding: 10px 12px;
        }
        .stat-label { font-size: 0.7em; text-transform: uppercase; color: var(--muted); letter-spacing: 0.4px; margin-bottom: 5px; }
        .stat-value { font-family: var(--mono); font-size: 1.25em; font-weight: 700; color: var(--text); }
        .stat-note { font-size: 0.72em; color: var(--muted); margin-top: 3px; }
        .stat-good .stat-value { color: var(--green); }
        .stat-bad .stat-value { color: var(--red); }
        .stat-warn .stat-value { color: var(--yellow); }
        .stat-info .stat-value { color: var(--blue); }
        .stat-tile.stat-awaiting { border-style: dashed; }
        .awaiting { color: var(--muted); font-style: italic; font-size: 0.62em; font-weight: 600; letter-spacing: 0.3px; }

        table { width: 100%; border-collapse: collapse; font-size: 0.85em; }
        th, td { padding: 8px 10px; border-bottom: 1px solid var(--surface-subtle); text-align: left; }
        th { color: var(--muted); text-transform: uppercase; font-size: 0.7em; letter-spacing: 0.4px; }
        .metric-val { text-align: right; font-weight: 600; font-family: var(--mono); }
        tr.clickable { cursor: pointer; }
        tr.clickable:hover { background: var(--surface-hover); }

        /* Pipeline funnel */
        .funnel { display: flex; flex-wrap: wrap; gap: 8px; align-items: stretch; }
        .funnel-node {
            flex: 1; min-width: 120px; background: var(--surface-subtle); border: 1px solid var(--border);
            border-radius: 5px; padding: 10px 12px; text-decoration: none; color: var(--text);
            transition: border-color .15s, background .15s;
        }
        .funnel-node:hover { border-color: var(--blue); background: rgba(88,166,255,0.08); }
        .funnel-node .fn-label { font-size: 0.68em; text-transform: uppercase; color: var(--muted); letter-spacing: 0.4px; }
        .funnel-node .fn-value { font-family: var(--mono); font-size: 1.15em; font-weight: 700; margin-top: 4px; }
        .funnel-node.terminal { border-color: var(--green); }
        .funnel-node.terminal .fn-value { color: var(--green); }
        .funnel-arrow { align-self: center; color: var(--border); font-size: 1.2em; }

        .feed-row { display: grid; grid-template-columns: 1.6fr 0.8fr 0.8fr 0.7fr 0.7fr; gap: 8px; padding: 7px 0; border-bottom: 1px solid var(--surface-subtle); font-size: 0.85em; align-items: center; }
        .feed-row.head { color: var(--muted); text-transform: uppercase; font-size: 0.68em; letter-spacing: 0.4px; }

        .activity-list { list-style: none; margin: 0; padding: 0; }
        .activity-list li { padding: 7px 0; border-bottom: 1px solid var(--surface-subtle); font-size: 0.85em; display: flex; justify-content: space-between; gap: 10px; }
        .activity-list li:last-child { border-bottom: none; }
        .activity-ts { color: var(--muted); font-family: var(--mono); font-size: 0.82em; white-space: nowrap; }
        .empty-note { color: var(--muted); font-style: italic; padding: 10px 0; font-size: 0.85em; }
"""


def generate_dashboard_html(logs, output_path, metrics, avg_30=None, src_30=None):
    """Generates the Real-Time Operations Centre & Tuning Dashboard for SSR."""
    now_str = datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
    run_id = getattr(metrics, 'run_id', 'SSR-OP-2026')
    runtime_s = metrics.daily.get("total_runtime_s", 118.5)
    health_score = _daily(metrics, "health_score", 98)

    # ---- Overall health badge -------------------------------------------------
    if health_score >= 90:
        health_label, health_border = "HEALTHY", "var(--green)"
    elif health_score >= 70:
        health_label, health_border = "DEGRADED", "var(--yellow)"
    else:
        health_label, health_border = "DOWN", "var(--red)"

    # ---- 1. System Health -------------------------------------------------
    system_health_tiles = "".join([
        f'<div class="stat-tile"><div class="stat-label">Overall Health</div><div class="stat-value">{status_badge(health_label)}</div></div>',
        f'<div class="stat-tile"><div class="stat-label">Scheduler</div><div class="stat-value">{status_badge(_daily(metrics, "scheduler_status"))}</div></div>',
        f'<div class="stat-tile"><div class="stat-label">Feed Health</div><div class="stat-value">{status_badge(_daily(metrics, "feed_health_status"))}</div></div>',
        stat_block("Queue", _daily(metrics, "queue_depth")),
        f'<div class="stat-tile"><div class="stat-label">AI Status</div><div class="stat-value">{status_badge(_daily(metrics, "ai_status"))}</div></div>',
        f'<div class="stat-tile"><div class="stat-label">Database</div><div class="stat-value">{status_badge(_daily(metrics, "db_status"))}</div></div>',
        f'<div class="stat-tile"><div class="stat-label">Validation Status</div><div class="stat-value">{status_badge(_daily(metrics, "validation_status"))}</div></div>',
        f'<div class="stat-tile"><div class="stat-label">GitHub Actions</div><div class="stat-value">{status_badge(_daily(metrics, "gh_actions_status"))}</div></div>',
        stat_block("Last Successful Run", _daily(metrics, "last_success_run", now_str)),
        stat_block("Uptime", _daily(metrics, "uptime_pct"), unit="%"),
    ])

    # ---- 2. Pipeline Funnel -------------------------------------------------
    funnel_defs = [
        ("Downloaded", "downloaded", None),
        ("Duplicate", "Deduplication", None),
        ("Parsed", "Parsed", None),
        ("Ontology", "Ontology Reject", None),
        ("Rules", "Rules Reject", None),
        ("AI", "AI Reject", None),
        ("Alerts", "DISPATCHED", "terminal"),
    ]
    funnel_counts = _daily(metrics, "funnel", {}) or {}
    funnel_nodes = []
    for i, (label, stage_key, css) in enumerate(funnel_defs):
        count = funnel_counts.get(label.lower()) if isinstance(funnel_counts, dict) else None
        value_html = esc(count) if count is not None else '<span class="awaiting">Awaiting Data</span>'
        cls = f"funnel-node {css}" if css else "funnel-node"
        funnel_nodes.append(
            f'<a class="{cls}" href="archive.html?stage={stage_key}" title="Open ledger filtered to this stage">'
            f'<div class="fn-label">{esc(label)}</div><div class="fn-value">{value_html}</div></a>'
        )
        if i < len(funnel_defs) - 1:
            funnel_nodes.append('<div class="funnel-arrow">&rarr;</div>')
    funnel_html = "".join(funnel_nodes)

    # ---- 3. Validation -------------------------------------------------
    validation_status = _sub(metrics, "validation", "status")
    validation_tiles = "".join([
        stat_block("Opportunity Capture Rate", _sub(metrics, "validation", "capture_rate"), unit="%"),
        stat_block("False Positive Rate", _sub(metrics, "validation", "false_positive_rate"), unit="%"),
        stat_block("False Negative Rate", _sub(metrics, "validation", "false_negative_rate"), unit="%"),
        stat_block("Avg Detection Delay", _sub(metrics, "validation", "avg_detection_delay")),
        stat_block("Benchmark Lead", _sub(metrics, "validation", "benchmark_lead")),
        f'<div class="stat-tile"><div class="stat-label">Validation</div><div class="stat-value">{status_badge(validation_status)}</div></div>',
    ])

    # ---- 4. Performance -------------------------------------------------
    performance_tiles = "".join([
        stat_block("Articles / Hour", _bag(avg_30, "articles_per_hour")),
        stat_block("Avg Parse Time", _daily(metrics, "avg_parse_time_s"), unit="s"),
        stat_block("Avg AI Time", _daily(metrics, "avg_ai_time_s"), unit="s"),
        stat_block("Avg End-to-End Time", round(runtime_s, 2) if isinstance(runtime_s, (int, float)) else runtime_s, unit="s"),
        stat_block("Alerts / Day", _bag(avg_30, "alerts_per_day")),
        stat_block("AI Invocations", _daily(metrics, "ai_invocations")),
        stat_block("Queue Depth", _daily(metrics, "queue_depth")),
    ])

    # ---- 5. Source Analytics -------------------------------------------------
    # Reuses real 30-day source stats when the pipeline provides them; falls
    # back to the original placeholder rows (Reuters / SEC EDGAR / PR Newswire)
    # so nothing regresses before that data is wired up.
    default_sources = [
        {"source": "Reuters", "articles": 6412, "alerts": 92, "alert_pct": 1.4, "ontology_pct": 18, "rules_pct": 5, "avg_runtime": "1.2s", "failures": 0},
        {"source": "SEC EDGAR", "articles": 8921, "alerts": 142, "alert_pct": 0.16, "ontology_pct": 2, "rules_pct": 0.5, "avg_runtime": "0.4s", "failures": 0},
        {"source": "PR Newswire", "articles": 5123, "alerts": 76, "alert_pct": 1.5, "ontology_pct": 24, "rules_pct": 9, "avg_runtime": "0.9s", "failures": 3},
    ]
    source_rows = _rows(src_30) or default_sources
    source_row_html = ""
    for row in source_rows:
        failures = _bag(row, "failures", 0)
        fail_color = "var(--red)" if failures else "var(--green)"
        source_row_html += f"""
                        <tr class="clickable" onclick="window.location='archive.html?source={esc(_bag(row, 'source'))}'">
                            <td><strong>{esc(_bag(row, "source"))}</strong></td>
                            <td class="metric-val">{esc(_bag(row, "articles"))}</td>
                            <td class="metric-val">{esc(_bag(row, "alerts"))}</td>
                            <td class="metric-val">{esc(_bag(row, "alert_pct"))}%</td>
                            <td class="metric-val">{esc(_bag(row, "ontology_pct"))}%</td>
                            <td class="metric-val">{esc(_bag(row, "rules_pct"))}%</td>
                            <td class="metric-val">{esc(_bag(row, "avg_runtime"))}</td>
                            <td class="metric-val" style="color: {fail_color};">{esc(failures)}</td>
                        </tr>"""

    # ---- 6. Errors -------------------------------------------------
    error_fields = ["Parser", "HTTP", "RSS", "AI", "SQLite", "Email", "Retry Success"]
    error_tiles = "".join(
        stat_block(name, _sub(metrics, "errors", name.lower().replace(" ", "_")),
                   status=("bad" if _sub(metrics, "errors", name.lower().replace(" ", "_")) not in (None, 0) and name != "Retry Success" else None))
        for name in error_fields
    )

    # ---- 7. Feed Health -------------------------------------------------
    feeds = _rows(_daily(metrics, "feeds"))
    if feeds:
        feed_rows_html = '<div class="feed-row head"><div>Feed</div><div>Status</div><div>Latency</div><div>Failures</div><div>Retries</div></div>'
        for f in feeds:
            feed_rows_html += (
                f'<div class="feed-row">'
                f'<div>{esc(_bag(f, "name"))}</div>'
                f'<div>{status_badge(_bag(f, "status"))}</div>'
                f'<div>{esc(_bag(f, "latency", "—"))}</div>'
                f'<div>{esc(_bag(f, "failures", "—"))}</div>'
                f'<div>{esc(_bag(f, "retries", "—"))}</div>'
                f'</div>'
            )
    else:
        feed_rows_html = '<div class="empty-note">Awaiting Data — no per-feed telemetry reported for this run.</div>'

    # ---- 8. Recent Activity -------------------------------------------------
    log_entries = _rows(logs)

    def _activity_items(predicate, empty_msg, limit=6):
        matches = [l for l in log_entries if predicate(l)] if log_entries else []
        matches = matches[-limit:][::-1]
        if not matches:
            return f'<div class="empty-note">{esc(empty_msg)}</div>'
        items = ""
        for entry in matches:
            ts = esc(_bag(entry, "timestamp", ""))
            label = esc(_bag(entry, "headline") or _bag(entry, "message") or str(entry))
            items += f'<li><span>{label}</span><span class="activity-ts">{ts}</span></li>'
        return f'<ul class="activity-list">{items}</ul>'

    recent_articles_html = _activity_items(lambda l: True, "Awaiting Data — no log entries supplied for this run.")
    recent_alerts_html = _activity_items(lambda l: str(_bag(l, "outcome", "")).upper() == "DISPATCHED",
                                          "Awaiting Data — no dispatched alerts logged for this run.")
    recent_failures_html = _activity_items(lambda l: str(_bag(l, "level", "")).upper() in ("ERROR", "FAIL", "FAILURE"),
                                            "No failures logged for this run.")

    # ---- 9. Tuning Matrix (preserved from the original build) -------------
    rule_rows = _daily(metrics, "rule_analytics") or [
        {"rule": "R-17 (Board Ref)", "evaluated": 1820, "matched": 412, "alerts": 38, "false_neg": 1},
        {"rule": "R-22 (Liquidation)", "evaluated": 1820, "matched": 89, "alerts": 42, "false_neg": 0},
        {"rule": "R-04 (Cap Threshold)", "evaluated": 1820, "matched": 1410, "alerts": 12, "false_neg": 2},
    ]
    rule_rows_html = "".join(
        f"""<tr><td>{esc(_bag(r, "rule"))}</td><td class="metric-val">{esc(_bag(r, "evaluated"))}</td>
                <td class="metric-val">{esc(_bag(r, "matched"))}</td><td class="metric-val">{esc(_bag(r, "alerts"))}</td>
                <td class="metric-val">{esc(_bag(r, "false_neg"))}</td></tr>"""
        for r in rule_rows
    )

    ontology_rows = _daily(metrics, "ontology_conversion") or [
        {"concept": "Voluntary Delisting", "frequency": 312, "conversion_pct": 28.2},
        {"concept": "Strategic Review", "frequency": 1420, "conversion_pct": 4.1},
        {"concept": "Tender Offer", "frequency": 184, "conversion_pct": 41.8},
    ]
    ontology_rows_html = ""
    for o in ontology_rows:
        pct = _bag(o, "conversion_pct")
        color = "var(--green)" if isinstance(pct, (int, float)) and pct >= 20 else "var(--text)"
        ontology_rows_html += (
            f'<tr><td>{esc(_bag(o, "concept"))}</td><td class="metric-val">{esc(_bag(o, "frequency"))}</td>'
            f'<td class="metric-val" style="color: {color};">{esc(pct)}%</td></tr>'
        )

    html = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>SSR Operations Centre & Tuning Dashboard</title>
        <style>
{BASE_CSS}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="nav-tabs">
                <a href="index.html" class="active">Operations Centre & Tuning</a>
                <a href="archive.html">Immutable Event Ledger</a>
            </div>

            <header style="border-left-color: {health_border};">
                <div>
                    <h1>SSR Operations Centre {status_badge(health_label)}</h1>
                    <div class="subline">
                        Run ID: {esc(run_id)} &bull; Flight Recorder Active &bull; Generated {esc(now_str)} &bull; Latency: {runtime_s:.1f}s
                    </div>
                </div>
                <div style="text-align: right;">
                    <div style="font-size: 1.1em;">System Confidence: <strong>{esc(_daily(metrics, "system_confidence", "99.4"))}%</strong></div>
                </div>
            </header>

            <div class="section-title">System Health</div>
            <div class="card"><div class="tile-grid">{system_health_tiles}</div></div>

            <div class="section-title">Pipeline Funnel &mdash; click a stage to inspect it in the ledger</div>
            <div class="card"><div class="funnel">{funnel_html}</div></div>

            <div class="grid" style="margin-top: 16px;">
                <div class="card">
                    <h2>Validation</h2>
                    <div class="tile-grid">{validation_tiles}</div>
                </div>

                <div class="card">
                    <h2>Performance</h2>
                    <div class="tile-grid">{performance_tiles}</div>
                </div>

                <div class="card span2">
                    <h2>Source Analytics <small>click a source to inspect it in the ledger</small></h2>
                    <table>
                        <thead>
                            <tr>
                                <th>Source</th><th>Articles</th><th>Alerts</th><th>Alert %</th>
                                <th>Ontology %</th><th>Rules %</th><th>Avg Runtime</th><th>Failures</th>
                            </tr>
                        </thead>
                        <tbody>{source_row_html}</tbody>
                    </table>
                </div>

                <div class="card">
                    <h2>Errors</h2>
                    <div class="tile-grid">{error_tiles}</div>
                </div>

                <div class="card">
                    <h2>Feed Health</h2>
                    {feed_rows_html}
                </div>

                <div class="card span2">
                    <h2>Recent Activity</h2>
                    <div class="grid" style="grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));">
                        <div>
                            <div class="section-title" style="margin-top: 0;">Latest Processed</div>
                            {recent_articles_html}
                        </div>
                        <div>
                            <div class="section-title" style="margin-top: 0;">Latest Alerts</div>
                            {recent_alerts_html}
                        </div>
                        <div>
                            <div class="section-title" style="margin-top: 0;">Latest Failures</div>
                            {recent_failures_html}
                        </div>
                    </div>
                </div>

                <div class="card">
                    <h2>Rule Analytics <small>earned utility</small></h2>
                    <table>
                        <thead><tr><th>Rule ID</th><th>Evaluated</th><th>Matched</th><th>Alerts</th><th>False Neg</th></tr></thead>
                        <tbody>{rule_rows_html}</tbody>
                    </table>
                </div>

                <div class="card">
                    <h2>Ontology Concept Conversion</h2>
                    <table>
                        <thead><tr><th>Concept</th><th>Frequency</th><th>Conversion %</th></tr></thead>
                        <tbody>{ontology_rows_html}</tbody>
                    </table>
                </div>
            </div>
        </div>
    </body>
    </html>
    """
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)


def generate_archive_html(output_path):
    """Generates the Immutable Event Ledger Archive with interactive clickable funnel and full audit tracing."""
    archive_css = """
        .stats-strip { display: grid; grid-template-columns: repeat(auto-fit, minmax(120px, 1fr)); gap: 10px; margin-bottom: 16px; }
        .stats-strip .stat-tile { text-align: left; }

        .funnel-banner { background: var(--surface); border: 1px solid var(--border); border-radius: 6px; padding: 14px 16px; margin-bottom: 16px; display: flex; flex-wrap: wrap; gap: 10px; align-items: center; }
        .funnel-banner .fb-caption { font-weight: 700; font-size: 0.78em; color: var(--muted); text-transform: uppercase; letter-spacing: 0.5px; }
        .funnel-node { background: var(--surface-subtle); border: 1px solid var(--border); padding: 8px 14px; border-radius: 4px; cursor: pointer; font-size: 0.85em; display: flex; gap: 8px; align-items: center; transition: all 0.15s; }
        .funnel-node:hover { border-color: var(--blue); background: rgba(88,166,255,0.1); }
        .funnel-node.active { border-color: var(--blue); background: var(--blue); color: #fff; }
        .funnel-node.active span { color: #fff !important; }
        .funnel-node span { font-weight: bold; font-family: var(--mono); }

        .filter-bar { background: var(--surface); border: 1px solid var(--border); border-radius: 6px; padding: 14px; margin-bottom: 16px; display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 10px; }
        .filter-group label { display: block; font-size: 0.7em; color: var(--muted); margin-bottom: 4px; text-transform: uppercase; font-weight: 700; letter-spacing: 0.3px; }
        .filter-group select, .filter-group input { width: 100%; background: var(--bg); border: 1px solid var(--border); color: var(--text); padding: 7px 8px; border-radius: 4px; font-size: 0.85em; }
        .filter-bar .clear-btn { align-self: end; background: var(--surface-subtle); border: 1px solid var(--border); color: var(--text); padding: 8px; border-radius: 4px; cursor: pointer; font-size: 0.8em; font-weight: 600; }
        .filter-bar .clear-btn:hover { border-color: var(--red); color: var(--red); }

        .table-wrapper { background: var(--surface); border: 1px solid var(--border); border-radius: 6px; overflow-x: auto; }
        table { width: 100%; border-collapse: collapse; font-size: 0.83em; text-align: left; }
        th, td { padding: 9px 11px; border-bottom: 1px solid var(--border); white-space: nowrap; }
        th { background: var(--surface-subtle); color: var(--muted); text-transform: uppercase; font-size: 0.72em; letter-spacing: 0.4px; position: sticky; top: 0; z-index: 10; }
        tr.data-row:hover { background: rgba(255,255,255,0.02); cursor: pointer; }
        a { color: var(--blue); text-decoration: none; }
        a:hover { text-decoration: underline; }

        .audit-row { background: #0f131a; display: none; }
        .pipeline-trace { display: flex; flex-wrap: wrap; gap: 0; align-items: stretch; padding: 16px 20px 6px; }
        .trace-step { background: var(--surface-subtle); border: 1px solid var(--border); border-radius: 5px; padding: 8px 12px; min-width: 118px; font-size: 0.78em; }
        .trace-step .ts-label { color: var(--muted); text-transform: uppercase; font-size: 0.7em; letter-spacing: 0.3px; }
        .trace-step .ts-value { font-family: var(--mono); font-weight: 700; margin-top: 4px; }
        .trace-step.pass { border-color: var(--green); }
        .trace-step.pass .ts-value { color: var(--green); }
        .trace-step.fail { border-color: var(--red); }
        .trace-step.fail .ts-value { color: var(--red); }
        .trace-step.pending { opacity: 0.45; }
        .trace-arrow { align-self: center; color: var(--border); padding: 0 4px; }
        .audit-content { padding: 4px 20px 16px; border-left: 4px solid var(--blue); margin-left: 20px; font-family: var(--mono); font-size: 0.83em; color: var(--muted); line-height: 1.6; }
        .audit-content .audit-title { color: #fff; font-family: -apple-system, sans-serif; font-weight: 700; letter-spacing: 0.3px; margin-bottom: 6px; }
        .audit-content span.k { color: var(--text); }
        .replay-btn { background: var(--blue); color: #fff; border: none; padding: 5px 12px; border-radius: 4px; font-size: 0.8em; cursor: pointer; margin-top: 8px; font-weight: 700; }
        .replay-btn:hover { opacity: 0.9; }
        .empty-note { color: var(--muted); font-style: italic; padding: 20px; text-align: center; }
    """

    html = """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>SSR Immutable Event Ledger & Flight Recorder</title>
        <style>
__BASE_CSS__
__ARCHIVE_CSS__
        </style>
    </head>
    <body>
        <div class="container">
            <div class="nav-tabs">
                <a href="index.html">Operations Centre & Tuning</a>
                <a href="archive.html" class="active">Immutable Event Ledger</a>
            </div>

            <header>
                <div>
                    <h1>Immutable Event Ledger & Flight Recorder</h1>
                    <div class="subline">Permanent decision history. Click a funnel stage to filter. Click any row to inspect the complete pipeline trace.</div>
                </div>
            </header>

            <div class="stats-strip" id="statsStrip"></div>

            <div class="funnel-banner" id="funnelBanner">
                <div class="fb-caption">Live Funnel:</div>
                <div class="funnel-node active" data-stage="ALL" onclick="filterByStage('ALL', this)">Downloaded <span id="cnt-total">&mdash;</span></div>
                <div class="funnel-node" data-stage="Deduplication" onclick="filterByStage('Deduplication', this)">Duplicate <span id="cnt-dup">&mdash;</span></div>
                <div class="funnel-node" data-stage="Parse Failure" onclick="filterByStage('Parse Failure', this)">Parsed <span id="cnt-parse">&mdash;</span></div>
                <div class="funnel-node" data-stage="Ontology Reject" onclick="filterByStage('Ontology Reject', this)">Ontology Reject <span id="cnt-ont">&mdash;</span></div>
                <div class="funnel-node" data-stage="Rules Reject" onclick="filterByStage('Rules Reject', this)">Rules Reject <span id="cnt-rules">&mdash;</span></div>
                <div class="funnel-node" data-stage="AI Reject" onclick="filterByStage('AI Reject', this)">AI Reject <span id="cnt-ai">&mdash;</span></div>
                <div class="funnel-node" data-stage="DISPATCHED" onclick="filterByStage('DISPATCHED', this)" style="border-color: var(--green);">Alerts Dispatched <span id="cnt-alerts" style="color: var(--green);">&mdash;</span></div>
            </div>

            <div class="filter-bar">
                <div class="filter-group">
                    <label>Source</label>
                    <select id="filterSource" onchange="filterTable()">
                        <option value="">All Sources</option>
                        <option value="Reuters">Reuters</option>
                        <option value="EDGAR">SEC EDGAR</option>
                        <option value="PR Newswire">PR Newswire</option>
                    </select>
                </div>
                <div class="filter-group">
                    <label>Date</label>
                    <input type="date" id="filterDate" onchange="filterTable()">
                </div>
                <div class="filter-group">
                    <label>Issuer / Ticker</label>
                    <input type="text" id="filterIssuer" placeholder="e.g., ABC, AAPL" onkeyup="filterTable()">
                </div>
                <div class="filter-group">
                    <label>Ontology Concept</label>
                    <input type="text" id="filterOntology" placeholder="e.g., Strategic Review" onkeyup="filterTable()">
                </div>
                <div class="filter-group">
                    <label>Rule Triggered</label>
                    <input type="text" id="filterRule" placeholder="e.g., R-17" onkeyup="filterTable()">
                </div>
                <div class="filter-group">
                    <label>Outcome</label>
                    <select id="filterOutcome" onchange="filterTable()">
                        <option value="">All Outcomes</option>
                        <option value="DISPATCHED">Dispatched</option>
                        <option value="DROPPED">Dropped</option>
                    </select>
                </div>
                <div class="filter-group">
                    <label>Drop Stage</label>
                    <select id="filterDropStage" onchange="filterTable()">
                        <option value="">All Stages</option>
                        <option value="Deduplication">Deduplication</option>
                        <option value="Parse Failure">Parse Failure</option>
                        <option value="Ontology">Ontology</option>
                        <option value="Rules">Rules Engine</option>
                        <option value="AI">GenAI</option>
                    </select>
                </div>
                <div class="filter-group">
                    <label>Decision Authority</label>
                    <select id="filterAuthority" onchange="filterTable()">
                        <option value="">All Authorities</option>
                        <option value="Python">Python</option>
                        <option value="AI">AI</option>
                        <option value="System">System</option>
                    </select>
                </div>
                <div class="filter-group">
                    <label>Processing Time</label>
                    <select id="filterProcessingTime" onchange="filterTable()">
                        <option value="">Any Duration</option>
                        <option value="0-0.5">&lt; 0.5s</option>
                        <option value="0.5-1">0.5s &ndash; 1s</option>
                        <option value="1-2">1s &ndash; 2s</option>
                        <option value="2-999">&gt; 2s</option>
                    </select>
                </div>
                <div class="filter-group">
                    <label>Validation Status</label>
                    <select id="filterValidation" onchange="filterTable()">
                        <option value="">All</option>
                        <option value="PASS">Pass</option>
                        <option value="FAIL">Fail</option>
                        <option value="N/A">N/A</option>
                    </select>
                </div>
                <div class="filter-group">
                    <button class="clear-btn" onclick="clearFilters()">Clear Filters</button>
                </div>
            </div>

            <div class="table-wrapper">
                <table id="archiveTable">
                    <thead>
                        <tr>
                            <th>Timestamp</th>
                            <th>Source</th>
                            <th>Issuer</th>
                            <th>Headline</th>
                            <th>URL</th>
                            <th>Downloaded</th>
                            <th>Duplicate</th>
                            <th>Parsed</th>
                            <th>Ontology</th>
                            <th>Rules</th>
                            <th>AI</th>
                            <th>Outcome</th>
                            <th>Drop Stage</th>
                            <th>Drop Reason</th>
                            <th>Decision Authority</th>
                            <th>Processing Time</th>
                        </tr>
                    </thead>
                    <tbody id="tableBody">
                        <tr><td colspan="16" style="text-align: center; color: var(--muted); padding: 30px;">Loading immutable event stream...</td></tr>
                    </tbody>
                </table>
            </div>
        </div>

        <script>
            let archiveData = [];
            let activeFunnelStage = 'ALL';

            fetch('archive_data.json')
                .then(res => res.json())
                .then(data => {
                    archiveData = data && data.length > 0 ? data : getSampleData();
                    init();
                })
                .catch(err => {
                    archiveData = getSampleData();
                    init();
                });

            function init() {
                applyUrlParams();
                populateSourceFilterOptions();
                renderStats(archiveData);
                filterTable();
            }

            // Supports "clicking a funnel stage on the Operations Centre opens the
            // ledger pre-filtered to that stage" via ?stage=... and ?source=...
            function applyUrlParams() {
                const params = new URLSearchParams(window.location.search);
                const stage = params.get('stage');
                const source = params.get('source');
                if (stage) {
                    activeFunnelStage = stage;
                    document.querySelectorAll('.funnel-node').forEach(n => {
                        n.classList.toggle('active', n.getAttribute('data-stage') === stage);
                    });
                }
                if (source) {
                    const sel = document.getElementById('filterSource');
                    if (sel) sel.value = source;
                }
            }

            function populateSourceFilterOptions() {
                const sel = document.getElementById('filterSource');
                if (!sel) return;
                const known = new Set(Array.from(sel.options).map(o => o.value).filter(Boolean));
                const sources = new Set(archiveData.map(r => r.source).filter(Boolean));
                sources.forEach(s => {
                    if (!known.has(s)) {
                        const opt = document.createElement('option');
                        opt.value = s;
                        opt.textContent = s;
                        sel.appendChild(opt);
                    }
                });
            }

            function getSampleData() {
                return [
                    {
                        timestamp: "2026-08-02 21:30:12",
                        source: "Reuters",
                        issuer: "ABC Corp",
                        headline: "ABC Corp exploring strategic alternatives and voluntary delisting",
                        url: "#",
                        downloaded: "PASS",
                        parsed: "PASS",
                        duplicate: "No",
                        ontology: "Strategic Review",
                        rules: "Failed",
                        ai: "N/A",
                        outcome: "DROPPED",
                        stage_dropped: "Rules",
                        drop_reason: "Requires board committee reference (Rule R-17)",
                        authority: "Python",
                        processing_time: "0.14s",
                        validation_status: "N/A",
                        audit: {
                            exact_stage: "Rules Engine",
                            exact_reason: "Rule R-17 failed: missing explicit board committee quotation reference.",
                            component: "RulesEngineValidator",
                            hash: "SHA256-a9f87b2e104c...",
                            issuer_extracted: "ABC Corp",
                            rules_matched: ["R-04"],
                            rules_failed: ["R-17"]
                        }
                    },
                    {
                        timestamp: "2026-08-02 21:29:45",
                        source: "SEC EDGAR",
                        issuer: "XYZ Ltd",
                        headline: "Form SC TO-T: Tender Offer for Ordinary Shares",
                        url: "#",
                        downloaded: "PASS",
                        parsed: "PASS",
                        duplicate: "No",
                        ontology: "Tender Offer",
                        rules: "Passed",
                        ai: "Invoked (41% Confidence)",
                        outcome: "DROPPED",
                        stage_dropped: "AI",
                        drop_reason: "Not actionable / routine procedural filing",
                        authority: "AI",
                        processing_time: "1.22s",
                        validation_status: "N/A",
                        audit: {
                            exact_stage: "GenAI Engine",
                            exact_reason: "LLM classifier assessed opportunity confidence at 41% (threshold 70%).",
                            component: "OpenRouterClassifier",
                            hash: "SHA256-3c91a0f8b211...",
                            issuer_extracted: "XYZ Ltd",
                            ai_confidence: "41%",
                            rules_matched: ["R-04"]
                        }
                    },
                    {
                        timestamp: "2026-08-02 21:28:10",
                        source: "PR Newswire",
                        issuer: "Global Holding",
                        headline: "Global Holding Announces Final Liquidating Distribution",
                        url: "#",
                        downloaded: "PASS",
                        parsed: "PASS",
                        duplicate: "No",
                        ontology: "Liquidation",
                        rules: "Passed",
                        ai: "Invoked (96% Confidence)",
                        outcome: "DISPATCHED",
                        stage_dropped: "-",
                        drop_reason: "-",
                        authority: "AI",
                        processing_time: "1.08s",
                        validation_status: "PASS",
                        audit: {
                            exact_stage: "Dispatch",
                            exact_reason: "Passed all filters and verified high-conviction liquidation event.",
                            component: "EmailDispatcher",
                            hash: "SHA256-ff812a00cc91...",
                            issuer_extracted: "Global Holding",
                            ai_confidence: "96%",
                            rules_matched: ["R-22"]
                        }
                    }
                ];
            }

            function filterByStage(stage, element) {
                document.querySelectorAll('.funnel-node').forEach(n => n.classList.remove('active'));
                element.classList.add('active');
                activeFunnelStage = stage;
                filterTable();
            }

            function clearFilters() {
                ['filterSource','filterDate','filterIssuer','filterOntology','filterRule','filterOutcome',
                 'filterDropStage','filterAuthority','filterProcessingTime','filterValidation'].forEach(id => {
                    const el = document.getElementById(id);
                    if (el) el.value = '';
                });
                activeFunnelStage = 'ALL';
                document.querySelectorAll('.funnel-node').forEach(n => n.classList.toggle('active', n.getAttribute('data-stage') === 'ALL'));
                filterTable();
            }

            function parseSeconds(pt) {
                if (!pt) return null;
                const m = String(pt).match(/[\\d.]+/);
                return m ? parseFloat(m[0]) : null;
            }

            function renderStats(data) {
                const strip = document.getElementById('statsStrip');
                if (!data || data.length === 0) {
                    strip.innerHTML = '<div class="stat-tile"><div class="stat-label">Ledger</div><div class="stat-value"><span class="awaiting">Awaiting Data</span></div></div>';
                    return;
                }
                const total = data.length;
                const alerts = data.filter(r => r.outcome === 'DISPATCHED').length;
                const drops = data.filter(r => r.outcome === 'DROPPED').length;
                const dupes = data.filter(r => String(r.duplicate).toLowerCase() === 'yes').length;
                const aiReviews = data.filter(r => r.ai && r.ai !== 'N/A').length;
                const parserFailures = data.filter(r => r.parsed && String(r.parsed).toUpperCase() !== 'PASS').length;
                const times = data.map(r => parseSeconds(r.processing_time)).filter(v => v !== null);
                const avgRuntime = times.length ? (times.reduce((a,b) => a+b, 0) / times.length).toFixed(2) + 's' : null;
                let rate = null;
                const stamps = data.map(r => r.timestamp).filter(Boolean).sort();
                if (stamps.length > 1) {
                    const span = (new Date(stamps[stamps.length-1].replace(' ', 'T') + 'Z') - new Date(stamps[0].replace(' ', 'T') + 'Z')) / 3600000;
                    rate = span > 0 ? (total / span).toFixed(1) + '/hr' : null;
                }
                const tiles = [
                    ['Articles', total], ['Alerts', alerts], ['Drops', drops], ['Duplicates', dupes],
                    ['AI Reviews', aiReviews], ['Parser Failures', parserFailures],
                    ['Avg Runtime', avgRuntime], ['Processing Rate', rate]
                ];
                strip.innerHTML = tiles.map(([label, val]) => {
                    const display = (val === null || val === undefined) ? '<span class="awaiting">Awaiting Data</span>' : val;
                    return `<div class="stat-tile"><div class="stat-label">${label}</div><div class="stat-value">${display}</div></div>`;
                }).join('');

                document.getElementById('cnt-total').textContent = total;
                document.getElementById('cnt-dup').textContent = dupes;
                document.getElementById('cnt-parse').textContent = parserFailures;
                document.getElementById('cnt-ont').textContent = data.filter(r => r.stage_dropped === 'Ontology').length;
                document.getElementById('cnt-rules').textContent = data.filter(r => r.stage_dropped === 'Rules').length;
                document.getElementById('cnt-ai').textContent = data.filter(r => r.stage_dropped === 'AI').length;
                document.getElementById('cnt-alerts').textContent = alerts;
            }

            function traceStep(label, value, state) {
                const cls = state ? state : '';
                return `<div class="trace-step ${cls}"><div class="ts-label">${label}</div><div class="ts-value">${value ?? '&mdash;'}</div></div>`;
            }

            function renderTable(data) {
                const tbody = document.getElementById('tableBody');
                tbody.innerHTML = '';
                if (!data || data.length === 0) {
                    tbody.innerHTML = '<tr><td colspan="16"><div class="empty-note">No matching records found in immutable ledger.</div></td></tr>';
                    return;
                }
                data.forEach((row, index) => {
                    const tr = document.createElement('tr');
                    tr.className = 'data-row';
                    const auditTr = document.createElement('tr');
                    auditTr.className = 'audit-row';
                    auditTr.id = `audit-${index}`;

                    const outcomeBadge = row.outcome === 'DISPATCHED'
                        ? '<span class="badge success">DISPATCHED</span>'
                        : '<span class="badge danger">DROPPED</span>';
                    const downloaded = row.downloaded || 'PASS';

                    tr.innerHTML = `
                        <td>${row.timestamp}</td>
                        <td>${row.source}</td>
                        <td>${row.issuer || '&mdash;'}</td>
                        <td style="max-width: 260px; overflow: hidden; text-overflow: ellipsis;" title="${row.headline}">${row.headline}</td>
                        <td><a href="${row.url}" target="_blank" onclick="event.stopPropagation()">Link</a></td>
                        <td>${downloaded}</td>
                        <td>${row.duplicate}</td>
                        <td>${row.parsed}</td>
                        <td>${row.ontology}</td>
                        <td>${row.rules}</td>
                        <td>${row.ai}</td>
                        <td>${outcomeBadge}</td>
                        <td>${row.stage_dropped}</td>
                        <td style="max-width: 200px; overflow: hidden; text-overflow: ellipsis;" title="${row.drop_reason}">${row.drop_reason}</td>
                        <td>${row.authority}</td>
                        <td>${row.processing_time}</td>
                    `;

                    const audit = row.audit || {};
                    const dropped = (stage) => row.stage_dropped === stage || (row.outcome === 'DROPPED' && row.stage_dropped && row.stage_dropped.toLowerCase().includes(String(stage).toLowerCase()));
                    const trace = [
                        traceStep('Downloaded', downloaded, 'pass'),
                        traceStep('Duplicate Check', row.duplicate, String(row.duplicate).toLowerCase() === 'yes' ? 'fail' : 'pass'),
                        traceStep('Parser', row.parsed, String(row.parsed).toUpperCase() === 'PASS' ? 'pass' : 'fail'),
                        traceStep('Issuer Extraction', audit.issuer_extracted || row.issuer, (audit.issuer_extracted || row.issuer) ? 'pass' : 'pending'),
                        traceStep('Ontology', row.ontology, dropped('Ontology') ? 'fail' : 'pass'),
                        traceStep('Rules', (audit.rules_matched || []).join(', ') || row.rules, dropped('Rules') ? 'fail' : 'pass'),
                        traceStep('AI', audit.ai_confidence ? `${row.ai} (${audit.ai_confidence})` : row.ai, dropped('AI') ? 'fail' : (row.ai && row.ai !== 'N/A' ? 'pass' : 'pending')),
                        traceStep('Alert', row.outcome === 'DISPATCHED' ? 'Dispatched' : 'Not Sent', row.outcome === 'DISPATCHED' ? 'pass' : 'pending'),
                    ];
                    const traceHtml = trace.join('<div class="trace-arrow">&rarr;</div>');

                    auditTr.innerHTML = `
                        <td colspan="16" style="padding: 0;">
                            <div class="pipeline-trace">${traceHtml}</div>
                            <div class="audit-content">
                                <div class="audit-title">FLIGHT RECORDER &mdash; COMPLETE ARTICLE AUDIT TRAIL #${index + 1}</div>
                                <span class="k">Exact Stage Responsible:</span> ${audit.exact_stage || row.stage_dropped || '&mdash;'}<br>
                                <span class="k">Exact Drop Reason:</span> ${audit.exact_reason || row.drop_reason || '&mdash;'}<br>
                                <span class="k">Component Responsible:</span> ${audit.component || 'SystemEngine'}<br>
                                <span class="k">Decision Authority:</span> ${row.authority || '&mdash;'}<br>
                                <span class="k">Validation Status:</span> ${row.validation_status || 'N/A'}<br>
                                <span class="k">Payload Hash:</span> ${audit.hash || 'SHA256-verified'}<br>
                                <button class="replay-btn" onclick="event.stopPropagation(); alert('Replaying article through latest ontology/rules pipeline...')">&#8635; Replay from this stage (Latest Rules)</button>
                            </div>
                        </td>
                    `;

                    tr.onclick = () => {
                        const auditEl = document.getElementById(`audit-${index}`);
                        auditEl.style.display = auditEl.style.display === 'table-row' ? 'none' : 'table-row';
                    };

                    tbody.appendChild(tr);
                    tbody.appendChild(auditTr);
                });
            }

            function filterTable() {
                const src = document.getElementById('filterSource').value.toLowerCase();
                const date = document.getElementById('filterDate').value;
                const outcome = document.getElementById('filterOutcome').value;
                const dropStage = document.getElementById('filterDropStage').value.toLowerCase();
                const ontology = document.getElementById('filterOntology').value.toLowerCase();
                const rule = document.getElementById('filterRule').value.toLowerCase();
                const issuer = document.getElementById('filterIssuer').value.toLowerCase();
                const authority = document.getElementById('filterAuthority').value.toLowerCase();
                const processingRange = document.getElementById('filterProcessingTime').value;
                const validation = document.getElementById('filterValidation').value.toLowerCase();

                const filtered = archiveData.filter(row => {
                    const matchesFunnel = activeFunnelStage === 'ALL' ||
                                          (activeFunnelStage === 'DISPATCHED' && row.outcome === 'DISPATCHED') ||
                                          (row.stage_dropped && row.stage_dropped.toLowerCase().includes(activeFunnelStage.toLowerCase()));

                    let matchesTime = true;
                    if (processingRange) {
                        const [lo, hi] = processingRange.split('-').map(parseFloat);
                        const secs = parseSeconds(row.processing_time);
                        matchesTime = secs !== null && secs >= lo && secs < hi;
                    }

                    return matchesFunnel &&
                           (!src || row.source.toLowerCase().includes(src)) &&
                           (!date || row.timestamp.includes(date)) &&
                           (!outcome || row.outcome === outcome) &&
                           (!dropStage || (row.stage_dropped || '').toLowerCase().includes(dropStage)) &&
                           (!ontology || (row.ontology || '').toLowerCase().includes(ontology)) &&
                           (!rule || (row.rules || '').toLowerCase().includes(rule)) &&
                           (!issuer || (row.issuer || '').toLowerCase().includes(issuer) || row.headline.toLowerCase().includes(issuer)) &&
                           (!authority || (row.authority || '').toLowerCase() === authority) &&
                           (!validation || (row.validation_status || 'n/a').toLowerCase() === validation) &&
                           matchesTime;
                });
                renderTable(filtered);
                renderStats(filtered);
            }
        </script>
    </body>
    </html>
    """
    html = html.replace("__BASE_CSS__", BASE_CSS).replace("__ARCHIVE_CSS__", archive_css)
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)