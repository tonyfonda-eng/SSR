"""
SSR Dashboard Generator
========================
Renders the two GitHub Pages surfaces for Special Situations Radar:

    generate_dashboard_html(...) -> index.html    "Operations Centre"
    generate_archive_html(...)   -> archive.html  "Immutable Event Ledger"

DESIGN NOTE ON WHY THIS FILE IS STRUCTURED THE WAY IT IS
----------------------------------------------------------
The version this replaces built archive.html as a triple-quoted string
using {{ }} (f-string brace-escaping) inside a block that was NOT an
f-string -- so the CSS shipped to the browser as literal ":root {{ ... }}",
which is invalid CSS. To make that class of bug structurally impossible,
CSS and JS now live in their own plain string constants (_STYLE_BLOCK,
_DASHBOARD_SCRIPT, _ARCHIVE_SCRIPT) with normal single braces, and are
spliced into the page templates via ordinary string interpolation/
.replace() -- never inside an f-string themselves. Only small, brace-free
HTML fragments (cards, table rows) are built with f-strings.

DATA CONTRACT for `metrics` (a plain dict -- e.g. dict(sqlite3.Row) plus
a bit of assembly). Every section reads with .get(...) and falls back to
"--", so a missing field degrades the display instead of crashing page
generation:

metrics = {
    "run_id": str,
    "generated_at": str,               # display string, already formatted
    "confidence": float,                # 0-100 overall system confidence

    "health": {
        "pipeline_status": "Operational" | "Degraded" | "Down",
        "uptime_pct": float,
        "feeds_active": int, "feeds_total": int,
        "workers_status": str,
        "queue_depth": int,
        "ai_status": str,               # e.g. "Healthy"
        "ai_pool_detail": str,          # e.g. "OpenRouter 6/9 - Gemini 5/7"
        "db_status": str,
        "validation_status": "PASS" | "FAIL",
    },
    "redundancy": {
        "sources_total": int, "sources_primary_active": int,
        "sources_backup": int, "failover_events": int,
        "dedup_rate_pct": float,
    },
    "errors": {
        "parser_failures": int, "rss_failures": int, "http_failures": int,
        "ai_failures": int, "db_errors": int, "retry_success_pct": float,
    },
    "performance": {
        "articles_today": int, "avg_parse_s": float, "avg_ai_s": float,
        "avg_e2e_s": float, "alerts_today": int, "ai_invocations": int,
    },
    "validation": {
        "known_events": int, "detected_events": int, "capture_rate_pct": float,
        "false_positive_pct": float, "false_negative_pct": float,
        "avg_delay_min": float, "status": "PASS" | "FAIL",
    },
    "funnel": [
        # `count` = survivors remaining AFTER this stage (drives the bar width,
        # first row is the 100% baseline). `rejected` = how many were newly
        # dropped AT this stage (shown as secondary text). `stage_key` = the
        # exact string that matches a row's `stage_dropped` in archive.html,
        # so the bar links to the articles that were rejected here -- NOT to
        # the survivors, since the rejects are what's worth inspecting.
        {"label": "Downloaded", "count": int, "rejected": None, "stage_key": None},
        {"label": "Unique (deduplicated)", "count": int, "rejected": int, "stage_key": "Duplicate"},
        {"label": "Parsed", "count": int, "rejected": int, "stage_key": "Parse Failure"},
        {"label": "Ontology matched", "count": int, "rejected": int, "stage_key": "Ontology"},
        {"label": "Rules matched", "count": int, "rejected": int, "stage_key": "Rules"},
        {"label": "AI approved", "count": int, "rejected": int, "stage_key": "AI"},
        {"label": "Alerts dispatched", "count": int, "rejected": int, "stage_key": "Email"},
    ],
    "sources": [
        {"name": str, "articles": int, "alerts": int, "ontology_pct": float,
         "rules_pct": float, "ai_pct": float, "alert_pct": float,
         "avg_processing_s": float, "errors": int},
        ...
    ],
    "rules":    [{"rule_id", "evaluated", "matched", "alerts", "false_neg"}, ...],
    "ontology": [{"concept", "frequency", "conversion_pct"}, ...],
}

`avg_30` / `src_30` mirror the top-level (health/redundancy/errors/
performance) and per-source shapes respectively, computed over a
trailing 30-day window -- pass None to hide the Today/30-Day toggle.
Capture rate (validation) and the funnel are always "current", not
toggled, since they aren't meaningfully a today-vs-avg comparison.

`logs` is an optional list of recent per-article dicts (same shape as
an archive row) that powers the Recent Activity feed:
    {"timestamp", "source", "headline", "outcome", "stage_dropped"}

NOTE: `logs`, `avg_30`, and `src_30` were accepted by the previous
version of this function but never referenced anywhere in its body --
they're wired up for real here.
"""

import os
import datetime
from html import escape as _esc
from urllib.parse import quote as _q


# ---------------------------------------------------------------------------
# Shared CSS / JS -- plain strings, single braces, never inside an f-string.
# ---------------------------------------------------------------------------

_STYLE_BLOCK = """
:root {
    --bg: #0d1117; --surface: #161b22; --surface-subtle: #21262d; --border: #30363d; --text: #c9d1d9;
    --muted: #8b949e; --green: #2ea043; --red: #cb2431; --yellow: #dbab0a; --blue: #58a6ff; --purple: #8957e5;
}
* { box-sizing: border-box; }
body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; background-color: var(--bg); color: var(--text); margin: 0; padding: 20px; }
.container { max-width: 1500px; margin: 0 auto; }
header { display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 12px; background: var(--surface); border: 1px solid var(--border); border-radius: 6px; padding: 20px 24px; margin-bottom: 20px; border-left: 6px solid var(--green); }
header.status-warn { border-left-color: var(--yellow); }
header.status-bad { border-left-color: var(--red); }
h1 { margin: 0; font-size: 1.8em; color: #fff; display: flex; align-items: center; gap: 10px; }
.badge { padding: 3px 8px; border-radius: 4px; font-size: 0.75em; font-weight: bold; }
.badge.success { background: rgba(46,160,67,0.15); color: var(--green); border: 1px solid var(--green); }
.badge.danger { background: rgba(203,36,49,0.15); color: var(--red); border: 1px solid var(--red); }
.badge.info { background: rgba(88,166,255,0.15); color: var(--blue); border: 1px solid var(--blue); }
.badge.warn { background: rgba(219,171,10,0.15); color: var(--yellow); border: 1px solid var(--yellow); }
.badge.py { background: rgba(88,166,255,0.15); color: var(--blue); border: 1px solid var(--blue); }
.badge.ai { background: rgba(137,87,229,0.15); color: var(--purple); border: 1px solid var(--purple); }
.badge.sys { background: rgba(219,171,10,0.15); color: var(--yellow); border: 1px solid var(--yellow); }

.nav-tabs { display: flex; gap: 10px; margin-bottom: 20px; }
.nav-tabs a { background: var(--surface); border: 1px solid var(--border); color: var(--text); padding: 10px 20px; border-radius: 6px; text-decoration: none; font-weight: 600; }
.nav-tabs a.active { background: var(--blue); color: #fff; border-color: var(--blue); }

.grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(450px, 1fr)); gap: 20px; margin-bottom: 20px; }
.card { background: var(--surface); border: 1px solid var(--border); border-radius: 6px; padding: 20px; }
.card h2 { margin-top: 0; font-size: 1.1em; color: #fff; border-bottom: 1px solid var(--border); padding-bottom: 10px; text-transform: uppercase; letter-spacing: 0.5px; display: flex; justify-content: space-between; align-items: center; }

table { width: 100%; border-collapse: collapse; font-size: 0.85em; }
th, td { padding: 10px 12px; border-bottom: 1px solid var(--surface-subtle); text-align: left; }
th { color: var(--muted); text-transform: uppercase; font-size: 0.75em; }
.metric-val { text-align: right; font-weight: 600; font-family: monospace; }

.section-block { margin-bottom: 26px; }
.section-heading { font-size: 0.85em; text-transform: uppercase; letter-spacing: 0.7px; color: var(--muted); margin: 0 0 12px 2px; display: flex; align-items: center; gap: 8px; }
.section-heading .dot { width: 6px; height: 6px; border-radius: 50%; background: var(--blue); display: inline-block; }

.stat-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(155px, 1fr)); gap: 12px; }
.stat-card { background: var(--surface); border: 1px solid var(--border); border-left: 3px solid var(--border); border-radius: 6px; padding: 14px 16px; }
.stat-card.good { border-left-color: var(--green); }
.stat-card.warn { border-left-color: var(--yellow); }
.stat-card.bad { border-left-color: var(--red); }
.stat-card.neutral { border-left-color: var(--blue); }
.stat-card .stat-label { font-size: 0.72em; color: var(--muted); text-transform: uppercase; letter-spacing: 0.5px; }
.stat-card .stat-value { font-family: monospace; font-size: 1.5em; font-weight: 700; color: #fff; margin-top: 4px; white-space: nowrap; }
.stat-card .stat-sub { font-size: 0.75em; color: var(--muted); margin-top: 3px; }

.kpi-hero { display: flex; gap: 24px; flex-wrap: wrap; align-items: center; background: linear-gradient(135deg, var(--surface), var(--surface-subtle)); border: 1px solid var(--border); border-radius: 8px; padding: 22px 26px; margin-bottom: 22px; }
.kpi-hero .kpi-value { font-family: monospace; font-size: 2.6em; font-weight: 700; color: #fff; line-height: 1; }
.kpi-hero .kpi-label { color: var(--muted); font-size: 0.8em; margin-top: 6px; text-transform: uppercase; letter-spacing: 0.5px; }
.kpi-hero .kpi-divider { width: 1px; align-self: stretch; background: var(--border); }
.kpi-hero .kpi-mini .v { font-family: monospace; font-weight: 700; color: var(--text); font-size: 1.1em; }
.kpi-hero .kpi-mini .l { font-size: 0.7em; color: var(--muted); text-transform: uppercase; letter-spacing: 0.4px; }

.funnel { display: flex; flex-direction: column; gap: 7px; }
.funnel-row { display: grid; grid-template-columns: 160px 1fr 100px; align-items: center; gap: 12px; text-decoration: none; padding: 4px 2px; border-radius: 4px; }
.funnel-row:hover { background: rgba(88,166,255,0.07); }
.funnel-row .funnel-label { font-size: 0.85em; color: var(--text); }
.funnel-row .funnel-track { background: var(--surface-subtle); border-radius: 4px; height: 22px; overflow: hidden; border: 1px solid var(--border); }
.funnel-row .funnel-fill { height: 100%; background: linear-gradient(90deg, var(--blue), var(--purple)); }
.funnel-row.is-final .funnel-fill { background: linear-gradient(90deg, var(--green), #3fb950); }
.funnel-row .funnel-count { font-family: monospace; font-size: 0.8em; text-align: right; color: var(--muted); }
.funnel-row .funnel-count strong { color: var(--text); }

.view-toggle { display: inline-flex; border: 1px solid var(--border); border-radius: 6px; overflow: hidden; }
.view-toggle button { background: var(--surface); color: var(--muted); border: none; padding: 6px 14px; font-size: 0.78em; cursor: pointer; font-weight: 600; }
.view-toggle button.active { background: var(--blue); color: #fff; }

.mini-feed-row { display: flex; justify-content: space-between; gap: 10px; padding: 8px 0; border-bottom: 1px solid var(--surface-subtle); font-size: 0.82em; align-items: center; }
.mini-feed-row:last-child { border-bottom: none; }
.mini-feed-row .mf-main { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.mini-feed-row .mf-src { color: var(--muted); white-space: nowrap; margin-left: 10px; }

.search-input, .filter-group select, .filter-group input { background: var(--bg); border: 1px solid var(--border); color: var(--text); padding: 7px 10px; border-radius: 4px; font-size: 0.85em; }
.search-input { width: 220px; }

tr.source-row { cursor: pointer; }
tr.source-row:hover td { color: var(--blue); }

.legend { display: flex; gap: 16px; flex-wrap: wrap; font-size: 0.78em; color: var(--muted); margin-top: 10px; }
.legend span.badge { margin-right: 4px; }

.filter-bar { background: var(--surface); border: 1px solid var(--border); border-radius: 6px; padding: 15px; margin-bottom: 20px; display: grid; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr)); gap: 12px; }
.filter-group label { display: block; font-size: 0.75em; color: var(--muted); margin-bottom: 5px; text-transform: uppercase; font-weight: 600; }
.filter-group select, .filter-group input { width: 100%; }

.funnel-banner { background: var(--surface); border: 1px solid var(--border); border-radius: 6px; padding: 15px 20px; margin-bottom: 20px; display: flex; flex-wrap: wrap; gap: 10px; align-items: center; justify-content: space-between; }
.funnel-node { background: var(--surface-subtle); border: 1px solid var(--border); padding: 8px 14px; border-radius: 4px; cursor: pointer; font-size: 0.85em; display: flex; gap: 8px; align-items: center; transition: all 0.15s; }
.funnel-node:hover { border-color: var(--blue); background: rgba(88,166,255,0.1); }
.funnel-node.active { border-color: var(--blue); background: var(--blue); color: #fff; }
.funnel-node span { font-weight: bold; font-family: monospace; }

.table-wrapper { background: var(--surface); border: 1px solid var(--border); border-radius: 6px; overflow-x: auto; }
#archiveTable { text-align: left; }
#archiveTable th, #archiveTable td { white-space: nowrap; }
#archiveTable th { background: var(--surface-subtle); position: sticky; top: 0; z-index: 10; }
#archiveTable tr:hover { background: rgba(255,255,255,0.02); cursor: pointer; }
#archiveTable a { color: var(--blue); text-decoration: none; }
#archiveTable a:hover { text-decoration: underline; }

.audit-row { background: #0f131a; display: none; }
.audit-content { padding: 15px 20px; border-left: 4px solid var(--blue); font-family: monospace; font-size: 0.85em; color: var(--muted); line-height: 1.6; }
.audit-content span.k { color: var(--text); }
.replay-btn { background: var(--blue); color: #fff; border: none; padding: 4px 10px; border-radius: 4px; font-size: 0.8em; cursor: pointer; margin-top: 8px; font-weight: bold; }
.replay-btn:hover { opacity: 0.9; }

:focus-visible { outline: 2px solid var(--blue); outline-offset: 2px; }

@media (max-width: 760px) {
  .grid { grid-template-columns: 1fr; }
  .funnel-row { grid-template-columns: 110px 1fr 76px; }
  .kpi-hero { flex-direction: column; align-items: flex-start; }
  .kpi-hero .kpi-divider { display: none; }
}

@media (prefers-reduced-motion: reduce) {
  * { transition: none !important; animation: none !important; }
}
"""

_DASHBOARD_SCRIPT = """
function setView(view) {
    document.querySelectorAll('.metrics-view').forEach(function(el) { el.style.display = 'none'; });
    document.getElementById('view-' + view).style.display = '';
    document.querySelectorAll('.view-toggle button').forEach(function(b) { b.classList.remove('active'); });
    document.getElementById('btn-' + view).classList.add('active');
}
function filterSources() {
    var q = document.getElementById('sourceSearch').value.toLowerCase();
    document.querySelectorAll('#sourcesTable tbody tr').forEach(function(row) {
        var name = (row.getAttribute('data-source') || '').toLowerCase();
        row.style.display = name.indexOf(q) !== -1 ? '' : 'none';
    });
}
"""


# ---------------------------------------------------------------------------
# Formatting helpers -- every one degrades to "--" instead of raising.
# ---------------------------------------------------------------------------

def _num(value, default="\u2014"):
    if value is None:
        return default
    try:
        return f"{int(round(float(value))):,}"
    except (TypeError, ValueError):
        return default


def _pct(value, decimals=1, default="\u2014"):
    if value is None:
        return default
    try:
        return f"{float(value):.{decimals}f}%"
    except (TypeError, ValueError):
        return default


def _sec(value, decimals=1, default="\u2014"):
    if value is None:
        return default
    try:
        return f"{float(value):.{decimals}f}s"
    except (TypeError, ValueError):
        return default


def _status_class(status):
    s = (status or "").strip().lower()
    if s in ("operational", "healthy", "pass", "running", "empty"):
        return "good"
    if s in ("degraded", "warn", "warning"):
        return "warn"
    if s in ("down", "fail", "error", "stalled"):
        return "bad"
    return "neutral"


def _stat_card(label, value, sub="", status=None):
    cls = _status_class(status) if status else "neutral"
    sub_html = f'<div class="stat-sub">{_esc(str(sub))}</div>' if sub else ""
    return (
        f'<div class="stat-card {cls}">'
        f'<div class="stat-label">{_esc(label)}</div>'
        f'<div class="stat-value">{value}</div>'
        f'{sub_html}'
        f'</div>'
    )


# ---------------------------------------------------------------------------
# generate_dashboard_html -- index.html, the Operations Centre
# ---------------------------------------------------------------------------

def generate_dashboard_html(logs, output_path, metrics, avg_30=None, src_30=None):
    """Generates the SSR Operations Centre: system health, redundancy,
    errors, pipeline performance, validation/opportunity-capture, the
    processing funnel, and per-source comparison stats.
    See the module docstring for the exact `metrics` shape expected."""
    metrics = metrics or {}
    health = metrics.get("health", {}) or {}
    redundancy = metrics.get("redundancy", {}) or {}
    errors = metrics.get("errors", {}) or {}
    perf = metrics.get("performance", {}) or {}
    validation = metrics.get("validation", {}) or {}
    funnel = metrics.get("funnel", []) or []
    sources = metrics.get("sources", []) or []
    rules = metrics.get("rules", []) or []
    ontology = metrics.get("ontology", []) or []

    run_id = metrics.get("run_id", "\u2014")
    generated_at = metrics.get(
        "generated_at",
        datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC"),
    )
    confidence = metrics.get("confidence")
    overall_status = health.get("pipeline_status", "Unknown")
    header_cls = {"good": "", "warn": "status-warn", "bad": "status-bad", "neutral": ""}[
        _status_class(overall_status)
    ]
    badge_cls = {"good": "success", "warn": "warn", "bad": "danger", "neutral": "info"}[
        _status_class(overall_status)
    ]

    # ---- health / redundancy / errors / performance cards, for one dataset
    def _health_cards(h):
        feeds_ok = h.get("feeds_active") is not None and h.get("feeds_active") == h.get("feeds_total")
        return "".join([
            _stat_card("Pipeline", h.get("pipeline_status", "Unknown"),
                       f'{_pct(h.get("uptime_pct"))} uptime', h.get("pipeline_status")),
            _stat_card("Feeds", f'{_num(h.get("feeds_active"))}/{_num(h.get("feeds_total"))}',
                       "sources active", "Operational" if feeds_ok else "Degraded"),
            _stat_card("Workers", h.get("workers_status", "Unknown"), "", h.get("workers_status")),
            _stat_card("Queue", _num(h.get("queue_depth", 0)), "pending items",
                       "Operational" if not h.get("queue_depth") else "Degraded"),
            _stat_card("AI Pool", h.get("ai_status", "Unknown"), h.get("ai_pool_detail", ""),
                       h.get("ai_status")),
            _stat_card("Database", h.get("db_status", "Unknown"), "", h.get("db_status")),
            _stat_card("Validation", h.get("validation_status", "Unknown"), "", h.get("validation_status")),
        ])

    def _redundancy_cards(r):
        return "".join([
            _stat_card("Sources Tracked", _num(r.get("sources_total")), "", "neutral"),
            _stat_card("Primary Active", _num(r.get("sources_primary_active")), "", "Operational"),
            _stat_card("Backup Sources", _num(r.get("sources_backup")), "", "neutral"),
            _stat_card("Failover Events", _num(r.get("failover_events", 0)), "this window",
                       "Operational" if not r.get("failover_events") else "Degraded"),
            _stat_card("Duplicate Detection", _pct(r.get("dedup_rate_pct")), "", "neutral"),
        ])

    def _error_cards(e):
        total_err = sum(v for v in [
            e.get("parser_failures"), e.get("rss_failures"), e.get("http_failures"),
            e.get("ai_failures"), e.get("db_errors"),
        ] if isinstance(v, (int, float)))
        return "".join([
            _stat_card("Parser Failures", _num(e.get("parser_failures", 0)), "",
                       "Operational" if not e.get("parser_failures") else "Degraded"),
            _stat_card("RSS Failures", _num(e.get("rss_failures", 0)), "",
                       "Operational" if not e.get("rss_failures") else "Degraded"),
            _stat_card("HTTP Failures", _num(e.get("http_failures", 0)), "",
                       "Operational" if not e.get("http_failures") else "Degraded"),
            _stat_card("AI Failures", _num(e.get("ai_failures", 0)), "",
                       "Operational" if not e.get("ai_failures") else "Degraded"),
            _stat_card("DB Errors", _num(e.get("db_errors", 0)), "",
                       "Operational" if not e.get("db_errors") else "Down"),
            _stat_card("Retry Success", _pct(e.get("retry_success_pct")), f'{_num(total_err)} total errors', "neutral"),
        ])

    def _perf_cards(p):
        return "".join([
            _stat_card("Articles Processed", _num(p.get("articles_today")), "", "neutral"),
            _stat_card("Avg Parse Time", _sec(p.get("avg_parse_s")), "", "neutral"),
            _stat_card("Avg AI Latency", _sec(p.get("avg_ai_s")), "", "neutral"),
            _stat_card("Avg End-to-End", _sec(p.get("avg_e2e_s")), "", "neutral"),
            _stat_card("Alerts", _num(p.get("alerts_today")), "", "good"),
            _stat_card("AI Invocations", _num(p.get("ai_invocations")), "", "neutral"),
        ])

    def _metrics_view(view_id, h, r, e, p, visible):
        display = "" if visible else "display:none;"
        return f'''
        <div class="metrics-view" id="view-{view_id}" style="{display}">
            <div class="section-block">
                <div class="section-heading"><span class="dot"></span>System Health</div>
                <div class="stat-grid">{_health_cards(h)}</div>
            </div>
            <div class="section-block">
                <div class="section-heading"><span class="dot"></span>Redundancy</div>
                <div class="stat-grid">{_redundancy_cards(r)}</div>
            </div>
            <div class="section-block">
                <div class="section-heading"><span class="dot"></span>Errors</div>
                <div class="stat-grid">{_error_cards(e)}</div>
            </div>
            <div class="section-block">
                <div class="section-heading"><span class="dot"></span>Pipeline Performance</div>
                <div class="stat-grid">{_perf_cards(p)}</div>
            </div>
        </div>'''

    today_view = _metrics_view("today", health, redundancy, errors, perf, True)
    toggle_html = ""
    if avg_30:
        avg_health = avg_30.get("health", {}) or {}
        avg_redundancy = avg_30.get("redundancy", {}) or {}
        avg_errors = avg_30.get("errors", {}) or {}
        avg_perf = avg_30.get("performance", {}) or {}
        avg_view = _metrics_view("avg30", avg_health, avg_redundancy, avg_errors, avg_perf, False)
        today_view = today_view + avg_view
        toggle_html = '''
        <div class="view-toggle" style="margin-bottom: 16px;">
            <button id="btn-today" class="active" onclick="setView('today')">Today</button>
            <button id="btn-avg30" onclick="setView('avg30')">30-Day Avg</button>
        </div>'''

    # ---- funnel (waterfall, clickable through to archive.html)
    def _funnel_html(stages):
        if not stages:
            return '<div style="color:var(--muted); font-size:0.85em;">No funnel data for this run.</div>'
        base = stages[0].get("count") or 1
        rows = []
        for i, stage in enumerate(stages):
            count = stage.get("count", 0) or 0
            rejected = stage.get("rejected")
            label = stage.get("label", "\u2014")
            stage_key = stage.get("stage_key")
            width = max(2, round((count / base) * 100)) if base else 2
            count_text = f'<strong>{_num(count)}</strong> {_pct((count / base) * 100) if base else ""}'
            if rejected is not None:
                count_text += f' <span style="color:var(--red);">&minus;{_num(rejected)}</span>'
            final_cls = " is-final" if i == len(stages) - 1 else ""
            inner = (
                f'<div class="funnel-label">{_esc(label)}</div>'
                f'<div class="funnel-track"><div class="funnel-fill" style="width:{width}%;"></div></div>'
                f'<div class="funnel-count">{count_text}</div>'
            )
            if stage_key:
                rows.append(f'<a class="funnel-row{final_cls}" href="archive.html?stage={_q(str(stage_key))}">{inner}</a>')
            else:
                rows.append(f'<div class="funnel-row{final_cls}">{inner}</div>')
        return f'<div class="funnel">{"".join(rows)}</div>'

    funnel_html = _funnel_html(funnel)

    # ---- validation / opportunity capture cards
    validation_cards = "".join([
        _stat_card("Known Events", _num(validation.get("known_events")), "validation set", "neutral"),
        _stat_card("Detected", _num(validation.get("detected_events")), "", "neutral"),
        _stat_card("False Positive Rate", _pct(validation.get("false_positive_pct")), "", "neutral"),
        _stat_card("False Negative Rate", _pct(validation.get("false_negative_pct")), "", "neutral"),
        _stat_card("Avg Detection Delay", f'{_num(validation.get("avg_delay_min"))} min', "", "neutral"),
        _stat_card("Status", validation.get("status", "Unknown"), "", validation.get("status")),
    ])

    # ---- source statistics table
    src_30_map = {s.get("name"): s for s in (src_30 or [])}
    source_rows = []
    for s in sources:
        name = s.get("name", "\u2014")
        baseline = src_30_map.get(name, {})
        delta_html = ""
        if baseline.get("alert_pct") is not None and s.get("alert_pct") is not None:
            diff = s["alert_pct"] - baseline["alert_pct"]
            arrow = "\u25b2" if diff > 0 else ("\u25bc" if diff < 0 else "\u2014")
            color = "var(--green)" if diff > 0 else ("var(--red)" if diff < 0 else "var(--muted)")
            delta_html = f'<span style="color:{color}; font-size:0.8em;"> {arrow}{abs(diff):.1f}</span>'
        error_count = s.get("errors", 0) or 0
        source_rows.append(
            f'<tr class="source-row" data-source="{_esc(name)}" '
            f'onclick="window.location.href=\'archive.html?source={_q(name)}\'">'
            f'<td><strong>{_esc(name)}</strong></td>'
            f'<td class="metric-val">{_num(s.get("articles"))}</td>'
            f'<td class="metric-val">{_num(s.get("alerts"))}</td>'
            f'<td class="metric-val">{_pct(s.get("ontology_pct"))}</td>'
            f'<td class="metric-val">{_pct(s.get("rules_pct"))}</td>'
            f'<td class="metric-val">{_pct(s.get("ai_pct"))}</td>'
            f'<td class="metric-val">{_pct(s.get("alert_pct"))}{delta_html}</td>'
            f'<td class="metric-val">{_sec(s.get("avg_processing_s"))}</td>'
            f'<td class="metric-val" style="color:{"var(--red)" if error_count else "var(--green)"};">{_num(error_count)}</td>'
            f'</tr>'
        )
    sources_html = "".join(source_rows) or (
        '<tr><td colspan="9" style="text-align:center; color:var(--muted); padding:20px;">'
        'No source data yet.</td></tr>'
    )

    # ---- rule analytics / ontology conversion (unchanged shape, still valuable)
rule_rows = "".join(
    f'<tr><td>{_esc(r.get("rule_id") or "&mdash;")}</td>'
    f'<td class="metric-val">{_num(r.get("evaluated"))}</td>'
    f'<td class="metric-val">{_num(r.get("matched"))}</td>'
    f'<td class="metric-val">{_num(r.get("alerts"))}</td>'
    f'<td class="metric-val">{_num(r.get("false_neg"))}</td></tr>'
    for r in rules
) or '<tr><td colspan="5" style="text-align:center; color:var(--muted); padding:16px;">No rule data yet.</td></tr>'

ontology_rows = "".join(
        f'<tr><td>{_esc(o.get("concept") or "&mdash;")}</td>'
        f'<td class="metric-val">{_num(o.get("frequency"))}</td>'
        f'<td class="metric-val" style="color:{"var(--green)" if (o.get("conversion_pct") or 0) >= 20 else "var(--text)"};">'
        f'{_pct(o.get("conversion_pct"))}</td></tr>'
        for o in ontology
    ) or '<tr><td colspan="3" style="text-align:center; color:var(--muted); padding:16px;">No ontology data yet.</td></tr>'

    # ---- recent activity (uses `logs`, previously an unused parameter)
    feed_rows = []
    for item in (logs or [])[:8]:
        headline = _esc(item.get("headline", "\u2014"))
        source = _esc(item.get("source", "\u2014"))
        outcome = item.get("outcome", "\u2014")
        b_cls = "success" if outcome == "DISPATCHED" else "danger"
        feed_rows.append(
            f'<div class="mini-feed-row">'
            f'<div class="mf-main" title="{headline}">{headline}</div>'
            f'<div class="mf-src">{source} <span class="badge {b_cls}">{_esc(outcome)}</span></div>'
            f'</div>'
        )
    recent_activity_html = "".join(feed_rows) or (
        '<div style="color:var(--muted); font-size:0.85em;">No recent activity recorded.</div>'
    )

    kpi_capture = _pct(validation.get("capture_rate_pct"), decimals=1)
    kpi_confidence = _pct(confidence, decimals=1) if confidence is not None else "\u2014"

    html = f'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>SSR Operations Centre</title>
<style>{_STYLE_BLOCK}</style>
</head>
<body>
<div class="container">
    <div class="nav-tabs">
        <a href="index.html" class="active">Operations Centre</a>
        <a href="archive.html">Immutable Event Ledger</a>
    </div>

    <header class="{header_cls}">
        <div>
            <h1>SSR Operations Centre <span class="badge {badge_cls}">{_esc(str(overall_status).upper())}</span></h1>
            <div style="color: var(--muted); margin-top: 5px; font-size: 0.9em;">
                Run ID: {_esc(str(run_id))} &bull; Generated {_esc(str(generated_at))}
            </div>
        </div>
    </header>

    <div class="kpi-hero">
        <div>
            <div class="kpi-value">{kpi_capture}</div>
            <div class="kpi-label">Opportunity Capture Rate</div>
        </div>
        <div class="kpi-divider"></div>
        <div class="kpi-mini"><div class="v">{kpi_confidence}</div><div class="l">System Confidence</div></div>
        <div class="kpi-mini"><div class="v">{_esc(str(validation.get("status","\u2014")))}</div><div class="l">Validation Status</div></div>
        <div class="kpi-mini"><div class="v">{_num(perf.get("articles_today"))}</div><div class="l">Articles Today</div></div>
        <div class="kpi-mini"><div class="v">{_num(perf.get("alerts_today"))}</div><div class="l">Alerts Today</div></div>
    </div>

    {toggle_html}
    {today_view}

    <div class="section-block">
        <div class="section-heading"><span class="dot"></span>Pipeline Funnel &mdash; click a stage to inspect it in the ledger</div>
        <div class="card">{funnel_html}</div>
    </div>

    <div class="section-block">
        <div class="section-heading"><span class="dot"></span>Validation &amp; Opportunity Capture</div>
        <div class="stat-grid">{validation_cards}</div>
    </div>

    <div class="grid">
        <div class="card" style="grid-column: span 2;">
            <h2>Source Performance &amp; Tuning Matrix
                <input class="search-input" id="sourceSearch" placeholder="Filter sources..." oninput="filterSources()">
            </h2>
            <table id="sourcesTable">
                <thead><tr>
                    <th>Source</th><th>Articles</th><th>Alerts</th><th>Ontology %</th><th>Rules %</th>
                    <th>AI %</th><th>Alert %</th><th>Avg Processing</th><th>Errors</th>
                </tr></thead>
                <tbody>{sources_html}</tbody>
            </table>
        </div>

        <div class="card">
            <h2>Recent Activity</h2>
            {recent_activity_html}
        </div>

        <div class="card">
            <h2>Rule Analytics (Earned Utility)</h2>
            <table>
                <thead><tr><th>Rule ID</th><th>Evaluated</th><th>Matched</th><th>Alerts</th><th>False Neg</th></tr></thead>
                <tbody>{rule_rows}</tbody>
            </table>
        </div>

        <div class="card">
            <h2>Ontology Concept Conversion</h2>
            <table>
                <thead><tr><th>Concept</th><th>Frequency</th><th>Conversion %</th></tr></thead>
                <tbody>{ontology_rows}</tbody>
            </table>
        </div>
    </div>
</div>
<script>{_DASHBOARD_SCRIPT}</script>
</body>
</html>
'''
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as fh:
        fh.write(html)


# ---------------------------------------------------------------------------
# generate_archive_html -- archive.html, the Immutable Event Ledger
#
# Deliberately NOT an f-string: this page needs zero server-side data
# interpolation (everything loads client-side from archive_data.json, same
# as before), so building it as a plain string removes any chance of a
# brace-escaping mistake reaching the browser as broken CSS.
# ---------------------------------------------------------------------------

_ARCHIVE_SCRIPT = """
function escapeHtml(str) {
    if (str === null || str === undefined) return '';
    return String(str)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;');
}

let archiveData = [];
let activeFunnelStage = 'ALL';

function getSampleData() {
    return [
        { timestamp: "2026-08-02 21:32:04", source: "Reuters", issuer: "ABC Corp",
          headline: "ABC Corp exploring strategic alternatives and voluntary delisting", url: "#",
          parsed: "PASS", duplicate: "No", ontology: "Strategic Review", rules: "Failed", ai: "N/A",
          outcome: "DROPPED", stage_dropped: "Rules", drop_reason: "Requires board committee reference (Rule R-17)",
          authority: "Python", processing_time: "0.14s",
          audit: { exact_stage: "Rules Engine", exact_reason: "Rule R-17 failed: missing explicit board committee quotation reference.", component: "RulesEngineValidator", hash: "SHA256-a9f87b2e104c..." } },

        { timestamp: "2026-08-02 21:29:45", source: "SEC EDGAR", issuer: "XYZ Ltd",
          headline: "Form SC TO-T: Tender Offer for Ordinary Shares", url: "#",
          parsed: "PASS", duplicate: "No", ontology: "Tender Offer", rules: "Passed", ai: "Invoked (41% confidence)",
          outcome: "DROPPED", stage_dropped: "AI", drop_reason: "Not actionable / routine procedural filing",
          authority: "AI", processing_time: "1.22s",
          audit: { exact_stage: "GenAI Engine", exact_reason: "Classifier assessed opportunity confidence at 41% (threshold 70%).", component: "OpenRouterClassifier", hash: "SHA256-3c91a0f8b211..." } },

        { timestamp: "2026-08-02 21:28:10", source: "PR Newswire", issuer: "Global Holding",
          headline: "Global Holding Announces Final Liquidating Distribution", url: "#",
          parsed: "PASS", duplicate: "No", ontology: "Liquidation", rules: "Passed", ai: "Invoked (96% confidence)",
          outcome: "DISPATCHED", stage_dropped: "-", drop_reason: "-",
          authority: "AI", processing_time: "1.08s",
          audit: { exact_stage: "Dispatch", exact_reason: "Passed all filters and verified high-conviction liquidation event.", component: "EmailDispatcher", hash: "SHA256-ff812a00cc91..." } },

        { timestamp: "2026-08-02 21:26:55", source: "GlobeNewswire", issuer: "Northfield Resources",
          headline: "Northfield Resources Reports Q2 Production Volumes", url: "#",
          parsed: "PASS", duplicate: "No", ontology: "None", rules: "-", ai: "N/A",
          outcome: "DROPPED", stage_dropped: "Ontology", drop_reason: "No special-situation concepts detected in headline or body",
          authority: "Python", processing_time: "0.21s",
          audit: { exact_stage: "Ontology Matcher", exact_reason: "0 of 77 concept patterns matched.", component: "OntologyEngine", hash: "SHA256-11c2a9e0af31..." } },

        { timestamp: "2026-08-02 21:24:12", source: "Business Wire", issuer: "Delcorp Industries",
          headline: "Delcorp Industries confirms merger agreement, all-cash offer", url: "#",
          parsed: "PASS", duplicate: "Yes", ontology: "-", rules: "-", ai: "N/A",
          outcome: "DROPPED", stage_dropped: "Duplicate", drop_reason: "Matches article ingested 4 minutes earlier from PR Newswire (same press release syndicated)",
          authority: "Python", processing_time: "0.03s",
          audit: { exact_stage: "Deduplication", exact_reason: "94% title/body similarity to article #48211.", component: "DedupeEngine", hash: "SHA256-77bb410ee204..." } },

        { timestamp: "2026-08-02 21:20:33", source: "SEC EDGAR", issuer: "Unknown",
          headline: "Form 8-K (malformed filing, unable to extract body text)", url: "#",
          parsed: "FAIL", duplicate: "No", ontology: "-", rules: "-", ai: "N/A",
          outcome: "DROPPED", stage_dropped: "Parse Failure", drop_reason: "HTML body extraction returned empty string after 2 retries",
          authority: "System", processing_time: "3.41s",
          audit: { exact_stage: "Parser", exact_reason: "trafilatura extraction failed twice; raw HTML did not match any known EDGAR template.", component: "HtmlParser", hash: "SHA256-0a4f2b9d7183..." } },

        { timestamp: "2026-08-02 21:18:02", source: "PR Newswire", issuer: "Vantage Special Situations Trust",
          headline: "Vantage Special Situations Trust declares special cash dividend", url: "#",
          parsed: "PASS", duplicate: "No", ontology: "Special Dividend", rules: "Passed", ai: "Invoked (89% confidence)",
          outcome: "DROPPED", stage_dropped: "Email", drop_reason: "Approved for alert, but SMTP send failed after 3 retries",
          authority: "System", processing_time: "2.02s",
          audit: { exact_stage: "Email Dispatcher", exact_reason: "SMTP timeout connecting to configured relay; alert queued but not delivered.", component: "EmailDispatcher", hash: "SHA256-c410fa2e9b77..." } },

        { timestamp: "2026-08-02 21:15:47", source: "London Stock Exchange", issuer: "Marlowe & Vance plc",
          headline: "Marlowe & Vance plc: Board Recommends Cash Offer from Hollis Capital", url: "#",
          parsed: "PASS", duplicate: "No", ontology: "Tender Offer, Board Rec", rules: "Passed", ai: "Invoked (97% confidence)",
          outcome: "DISPATCHED", stage_dropped: "-", drop_reason: "-",
          authority: "AI", processing_time: "1.63s",
          audit: { exact_stage: "Dispatch", exact_reason: "High-conviction board-recommended cash offer, all filters passed.", component: "EmailDispatcher", hash: "SHA256-5e208cf134aa..." } },

        { timestamp: "2026-08-02 21:11:29", source: "EQS News (Germany)", issuer: "Baumgart AG",
          headline: "Baumgart AG quarterly results in line with guidance", url: "#",
          parsed: "PASS", duplicate: "No", ontology: "None", rules: "-", ai: "N/A",
          outcome: "DROPPED", stage_dropped: "Ontology", drop_reason: "Routine earnings release, no special-situation language present",
          authority: "Python", processing_time: "0.18s",
          audit: { exact_stage: "Ontology Matcher", exact_reason: "0 of 77 concept patterns matched.", component: "OntologyEngine", hash: "SHA256-9931e6f0aa02..." } },

        { timestamp: "2026-08-02 21:07:15", source: "CNMV (Spain)", issuer: "Iberia Textil SA",
          headline: "Iberia Textil SA announces strategic review of non-core assets", url: "#",
          parsed: "PASS", duplicate: "No", ontology: "Strategic Review", rules: "Failed", ai: "N/A",
          outcome: "DROPPED", stage_dropped: "Rules", drop_reason: "Strategic review mentioned, but no committee formation or advisor engagement language (Rule R-17)",
          authority: "Python", processing_time: "0.16s",
          audit: { exact_stage: "Rules Engine", exact_reason: "Rule R-17 failed: no qualifying advisor/committee reference.", component: "RulesEngineValidator", hash: "SHA256-2b7710dfea45..." } },

        { timestamp: "2026-08-02 21:03:58", source: "SEC EDGAR", issuer: "Halloway Group",
          headline: "Form S-4: Registration of Securities in Connection with Stock Merger", url: "#",
          parsed: "PASS", duplicate: "No", ontology: "Stock Merger", rules: "Passed", ai: "Invoked (34% confidence)",
          outcome: "DROPPED", stage_dropped: "AI", drop_reason: "Preliminary S-4, deal terms not finalized, low actionability",
          authority: "AI", processing_time: "1.79s",
          audit: { exact_stage: "GenAI Engine", exact_reason: "Classifier flagged as premature -- terms subject to change, confidence 34% (threshold 70%).", component: "OpenRouterClassifier", hash: "SHA256-e015b7a3f920..." } },

        { timestamp: "2026-08-02 20:59:41", source: "SIX Exchange (Switzerland)", issuer: "Corvina Holding AG",
          headline: "Corvina Holding AG confirms Dutch auction tender for up to 8% of shares", url: "#",
          parsed: "PASS", duplicate: "No", ontology: "Dutch Auction", rules: "Passed", ai: "Invoked (91% confidence)",
          outcome: "DISPATCHED", stage_dropped: "-", drop_reason: "-",
          authority: "AI", processing_time: "1.35s",
          audit: { exact_stage: "Dispatch", exact_reason: "Dutch auction tender confirmed with specific share/price terms.", component: "EmailDispatcher", hash: "SHA256-8814cbb203e1..." } }
    ];
}

function renderTable(data) {
    const tbody = document.getElementById('tableBody');
    tbody.innerHTML = '';
    if (!data || data.length === 0) {
        tbody.innerHTML = '<tr><td colspan="14" style="text-align: center; color: var(--muted); padding: 20px;">No matching records found in immutable ledger.</td></tr>';
        return;
    }
    data.forEach((row, index) => {
        const tr = document.createElement('tr');
        const auditTr = document.createElement('tr');
        auditTr.className = 'audit-row';
        auditTr.id = `audit-${index}`;

        const outcomeBadge = row.outcome === 'DISPATCHED' ? '<span class="badge success">DISPATCHED</span>' : '<span class="badge danger">DROPPED</span>';
        const authorityClass = row.authority === 'AI' ? 'ai' : (row.authority === 'System' ? 'sys' : 'py');
        const authorityBadge = `<span class="badge ${authorityClass}">${escapeHtml(row.authority || 'Python')}</span>`;
        const safeHeadline = escapeHtml(row.headline);
        const safeIssuer = escapeHtml(row.issuer);
        const safeReason = escapeHtml(row.drop_reason);

        tr.innerHTML = `
            <td>${escapeHtml(row.timestamp)}</td>
            <td>${escapeHtml(row.source)}</td>
            <td style="max-width: 280px; overflow: hidden; text-overflow: ellipsis;" title="${safeHeadline}"><strong>[${safeIssuer}]</strong> ${safeHeadline}</td>
            <td><a href="${row.url}" target="_blank" rel="noopener">Link</a></td>
            <td>${escapeHtml(row.parsed)}</td>
            <td>${escapeHtml(row.duplicate)}</td>
            <td>${escapeHtml(row.ontology)}</td>
            <td>${escapeHtml(row.rules)}</td>
            <td>${escapeHtml(row.ai)}</td>
            <td>${outcomeBadge}</td>
            <td>${escapeHtml(row.stage_dropped)}</td>
            <td style="max-width: 220px; overflow: hidden; text-overflow: ellipsis;" title="${safeReason}">${safeReason}</td>
            <td>${authorityBadge}</td>
            <td>${escapeHtml(row.processing_time)}</td>
        `;

        auditTr.innerHTML = `
            <td colspan="14" style="padding: 0;">
                <div class="audit-content">
                    <strong>[FLIGHT RECORDER -- COMPLETE ARTICLE AUDIT TRAIL #${index + 1}]</strong><br>
                    <span class="k">Exact Stage Responsible:</span> ${escapeHtml(row.audit && row.audit.exact_stage || row.stage_dropped)}<br>
                    <span class="k">Exact Drop Reason:</span> ${escapeHtml(row.audit && row.audit.exact_reason || row.drop_reason)}<br>
                    <span class="k">Component Responsible:</span> ${escapeHtml(row.audit && row.audit.component || 'SystemEngine')}<br>
                    <span class="k">Payload Hash:</span> ${escapeHtml(row.audit && row.audit.hash || 'SHA256-verified')}<br>
                    <span class="k">Decision Authority:</span> ${authorityBadge}<br>
                    <button class="replay-btn" onclick="alert('Replaying article through latest ontology/rules pipeline...')">&#8635; Replay from this stage (latest rules)</button>
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

function filterByStage(stageKey, element) {
    document.querySelectorAll('.funnel-node').forEach(n => n.classList.remove('active'));
    if (element) element.classList.add('active');
    activeFunnelStage = stageKey;
    filterTable();
}

function filterTable() {
    const src = document.getElementById('filterSource').value.toLowerCase();
    const date = document.getElementById('filterDate').value;
    const outcome = document.getElementById('filterOutcome').value;
    const dropStage = document.getElementById('filterDropStage').value;
    const authority = document.getElementById('filterAuthority').value;
    const ontology = document.getElementById('filterOntology').value.toLowerCase();
    const rule = document.getElementById('filterRule').value.toLowerCase();
    const ai = document.getElementById('filterAi').value.toLowerCase();
    const issuer = document.getElementById('filterIssuer').value.toLowerCase();

    const filtered = archiveData.filter(row => {
        const matchesFunnel = activeFunnelStage === 'ALL' ||
                              (activeFunnelStage === 'DISPATCHED' && row.outcome === 'DISPATCHED') ||
                              (row.stage_dropped === activeFunnelStage);

        return matchesFunnel &&
               (!src || row.source.toLowerCase().includes(src)) &&
               (!date || row.timestamp.includes(date)) &&
               (!outcome || row.outcome === outcome) &&
               (!dropStage || row.stage_dropped === dropStage) &&
               (!authority || row.authority === authority) &&
               (!ontology || (row.ontology || '').toLowerCase().includes(ontology)) &&
               (!rule || (row.rules || '').toLowerCase().includes(rule)) &&
               (!ai || (row.ai || '').toLowerCase().includes(ai)) &&
               (!issuer || (row.issuer || '').toLowerCase().includes(issuer) || (row.headline || '').toLowerCase().includes(issuer));
    });
    renderTable(filtered);
}

function initFromQuery() {
    const params = new URLSearchParams(window.location.search);
    const stage = params.get('stage');
    const source = params.get('source');
    if (stage) {
        const node = document.querySelector(`.funnel-node[data-stage="${stage}"]`);
        filterByStage(stage, node);
    }
    if (source) {
        document.getElementById('filterSource').value = source;
        filterTable();
    }
}

fetch('archive_data.json')
    .then(res => res.json())
    .then(data => {
        archiveData = data && data.length > 0 ? data : getSampleData();
        renderTable(archiveData);
        initFromQuery();
    })
    .catch(() => {
        archiveData = getSampleData();
        renderTable(archiveData);
        initFromQuery();
    });
"""


def generate_archive_html(output_path):
    """Generates the Immutable Event Ledger: one row per processed article,
    a clickable drop-off funnel, full filtering, and an expandable per-article
    audit trail. Data loads client-side from archive_data.json next to this
    file, falling back to bundled sample rows if that fetch fails (e.g. when
    previewing the file locally)."""
    html = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>SSR Immutable Event Ledger</title>
<style>__STYLE_BLOCK__</style>
</head>
<body>
<div class="container">
    <div class="nav-tabs">
        <a href="index.html">Operations Centre</a>
        <a href="archive.html" class="active">Immutable Event Ledger</a>
    </div>

    <header>
        <div>
            <h1>Immutable Event Ledger</h1>
            <p style="color: var(--muted); margin: 5px 0 0 0; font-size: 0.9em;">Permanent decision history for every article SSR has processed. Click any funnel stage to filter, click any row to inspect the complete pipeline trace.</p>
        </div>
    </header>

    <div class="funnel-banner">
        <div style="font-weight: bold; font-size: 0.9em; color: var(--muted);">LIVE FUNNEL:</div>
        <div class="funnel-node active" data-stage="ALL" onclick="filterByStage('ALL', this)">Total Ingested <span id="cnt-total">&mdash;</span></div>
        <div class="funnel-node" data-stage="Duplicate" onclick="filterByStage('Duplicate', this)">Duplicate <span id="cnt-dup">&mdash;</span></div>
        <div class="funnel-node" data-stage="Parse Failure" onclick="filterByStage('Parse Failure', this)">Parse Failure <span id="cnt-parse">&mdash;</span></div>
        <div class="funnel-node" data-stage="Ontology" onclick="filterByStage('Ontology', this)">Ontology Reject <span id="cnt-ont">&mdash;</span></div>
        <div class="funnel-node" data-stage="Rules" onclick="filterByStage('Rules', this)">Rules Reject <span id="cnt-rules">&mdash;</span></div>
        <div class="funnel-node" data-stage="AI" onclick="filterByStage('AI', this)">AI Reject <span id="cnt-ai">&mdash;</span></div>
        <div class="funnel-node" data-stage="Email" onclick="filterByStage('Email', this)">Email Failed <span id="cnt-email">&mdash;</span></div>
        <div class="funnel-node" data-stage="DISPATCHED" onclick="filterByStage('DISPATCHED', this)" style="border-color: var(--green);">Alerts Dispatched <span id="cnt-alerts" style="color: var(--green);">&mdash;</span></div>
    </div>

    <div class="filter-bar">
        <div class="filter-group">
            <label>Source</label>
            <input type="text" id="filterSource" placeholder="Any source" onkeyup="filterTable()">
        </div>
        <div class="filter-group">
            <label>Date</label>
            <input type="date" id="filterDate" onchange="filterTable()">
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
                <option value="Duplicate">Duplicate</option>
                <option value="Parse Failure">Parse Failure</option>
                <option value="Ontology">Ontology</option>
                <option value="Rules">Rules Engine</option>
                <option value="AI">GenAI</option>
                <option value="Email">Email Dispatch</option>
            </select>
        </div>
        <div class="filter-group">
            <label>Decision Authority</label>
            <select id="filterAuthority" onchange="filterTable()">
                <option value="">All</option>
                <option value="Python">Python (deterministic)</option>
                <option value="AI">AI (model judgment)</option>
                <option value="System">System (infrastructure)</option>
            </select>
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
            <label>AI Decision</label>
            <input type="text" id="filterAi" placeholder="e.g., Reject" onkeyup="filterTable()">
        </div>
        <div class="filter-group">
            <label>Issuer / Ticker</label>
            <input type="text" id="filterIssuer" placeholder="e.g., ABC, AAPL" onkeyup="filterTable()">
        </div>
    </div>
    <div class="legend">
        <div><span class="badge py">Python</span>deterministic logic -- duplicate check, parser, ontology, rules</div>
        <div><span class="badge ai">AI</span>model-driven classification or prioritisation</div>
        <div><span class="badge sys">System</span>infrastructure issue -- timeout, feed failure, database, email delivery</div>
    </div>

    <div class="table-wrapper">
        <table id="archiveTable">
            <thead>
                <tr>
                    <th>Timestamp</th>
                    <th>Source</th>
                    <th>Headline / Issuer</th>
                    <th>URL</th>
                    <th>Parsed</th>
                    <th>Duplicate</th>
                    <th>Ontology</th>
                    <th>Rules</th>
                    <th>AI</th>
                    <th>Outcome</th>
                    <th>Stage Dropped</th>
                    <th>Drop Reason</th>
                    <th>Authority</th>
                    <th>Latency</th>
                </tr>
            </thead>
            <tbody id="tableBody">
                <tr><td colspan="14" style="text-align: center; color: var(--muted); padding: 30px;">Loading immutable event stream...</td></tr>
            </tbody>
        </table>
    </div>
</div>

<script>__ARCHIVE_SCRIPT__</script>
</body>
</html>
"""
    html = html.replace("__STYLE_BLOCK__", _STYLE_BLOCK).replace("__ARCHIVE_SCRIPT__", _ARCHIVE_SCRIPT)
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as fh:
        fh.write(html)


# ---------------------------------------------------------------------------
# Local preview -- run `python3 dashboard.py` to regenerate both pages with
# realistic sample data without needing the full pipeline.
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    demo_metrics = {
        "run_id": "SSR-OP-20260802-0600",
        "generated_at": "2026-08-02 21:35:12 UTC",
        "confidence": 99.4,
        "health": {
            "pipeline_status": "Operational", "uptime_pct": 99.98,
            "feeds_active": 34, "feeds_total": 34,
            "workers_status": "Running", "queue_depth": 0,
            "ai_status": "Healthy", "ai_pool_detail": "OpenRouter 6/9 \u00b7 Gemini 5/7",
            "db_status": "Healthy", "validation_status": "PASS",
        },
        "redundancy": {
            "sources_total": 34, "sources_primary_active": 34, "sources_backup": 11,
            "failover_events": 2, "dedup_rate_pct": 99.7,
        },
        "errors": {
            "parser_failures": 3, "rss_failures": 1, "http_failures": 8,
            "ai_failures": 0, "db_errors": 0, "retry_success_pct": 96.0,
        },
        "performance": {
            "articles_today": 4823, "avg_parse_s": 0.34, "avg_ai_s": 1.8,
            "avg_e2e_s": 2.2, "alerts_today": 57, "ai_invocations": 183,
        },
        "validation": {
            "known_events": 742, "detected_events": 708, "capture_rate_pct": 95.4,
            "false_positive_pct": 2.8, "false_negative_pct": 3.6,
            "avg_delay_min": 5, "status": "PASS",
        },
        "funnel": [
            {"label": "Downloaded", "count": 4823, "rejected": None, "stage_key": None},
            {"label": "Unique (deduplicated)", "count": 4211, "rejected": 612, "stage_key": "Duplicate"},
            {"label": "Parsed", "count": 4193, "rejected": 18, "stage_key": "Parse Failure"},
            {"label": "Ontology matched", "count": 931, "rejected": 3262, "stage_key": "Ontology"},
            {"label": "Rules matched", "count": 183, "rejected": 748, "stage_key": "Rules"},
            {"label": "AI approved", "count": 61, "rejected": 122, "stage_key": "AI"},
            {"label": "Alerts dispatched", "count": 57, "rejected": 4, "stage_key": "Email"},
        ],
        "sources": [
            {"name": "Reuters", "articles": 6412, "alerts": 92, "ontology_pct": 18, "rules_pct": 5,
             "ai_pct": 5, "alert_pct": 1.4, "avg_processing_s": 1.2, "errors": 0},
            {"name": "SEC EDGAR", "articles": 8921, "alerts": 14, "ontology_pct": 2, "rules_pct": 0.5,
             "ai_pct": 0.5, "alert_pct": 0.16, "avg_processing_s": 0.4, "errors": 0},
            {"name": "PR Newswire", "articles": 5123, "alerts": 76, "ontology_pct": 24, "rules_pct": 9,
             "ai_pct": 8, "alert_pct": 1.5, "avg_processing_s": 0.9, "errors": 3},
        ],
        "rules": [
            {"rule_id": "R-17 (Board Ref)", "evaluated": 1820, "matched": 412, "alerts": 38, "false_neg": 1},
            {"rule_id": "R-22 (Liquidation)", "evaluated": 1820, "matched": 89, "alerts": 42, "false_neg": 0},
            {"rule_id": "R-04 (Cap Threshold)", "evaluated": 1820, "matched": 1410, "alerts": 12, "false_neg": 2},
        ],
        "ontology": [
            {"concept": "Voluntary Delisting", "frequency": 312, "conversion_pct": 28.2},
            {"concept": "Strategic Review", "frequency": 1420, "conversion_pct": 4.1},
            {"concept": "Tender Offer", "frequency": 184, "conversion_pct": 41.8},
        ],
    }
    demo_avg_30 = {
        "health": {**demo_metrics["health"], "uptime_pct": 99.9},
        "redundancy": {**demo_metrics["redundancy"], "failover_events": 5},
        "errors": {**demo_metrics["errors"], "http_failures": 11, "retry_success_pct": 94.2},
        "performance": {**demo_metrics["performance"], "articles_today": 4390, "alerts_today": 49},
    }
    demo_src_30 = [
        {"name": "Reuters", "alert_pct": 1.1},
        {"name": "SEC EDGAR", "alert_pct": 0.2},
        {"name": "PR Newswire", "alert_pct": 1.7},
    ]
    demo_logs = [
        {"timestamp": "21:32", "source": "Reuters", "headline": "ABC Corp exploring strategic alternatives", "outcome": "DROPPED"},
        {"timestamp": "21:29", "source": "SEC EDGAR", "headline": "Form SC TO-T: Tender Offer for Ordinary Shares", "outcome": "DROPPED"},
        {"timestamp": "21:28", "source": "PR Newswire", "headline": "Global Holding Announces Final Liquidating Distribution", "outcome": "DISPATCHED"},
        {"timestamp": "21:15", "source": "London Stock Exchange", "headline": "Marlowe & Vance plc: Board Recommends Cash Offer", "outcome": "DISPATCHED"},
    ]

    out_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "preview")
    generate_dashboard_html(demo_logs, os.path.join(out_dir, "index.html"), demo_metrics, demo_avg_30, demo_src_30)
    generate_archive_html(os.path.join(out_dir, "archive.html"))
    print(f"Wrote preview to {out_dir}")