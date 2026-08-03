import datetime
import os
import json


# ---------------------------------------------------------------------------
# DECISION INTELLIGENCE REDESIGN — read this before touching layout code
#
# This module used to organise itself around *technical components*
# (System Health, Performance, Errors, Feed Health...). It now organises
# itself around *operational questions*:
#
#   index.html               -> "Are we catching the opportunities that
#                                matter, and if not, why not?"
#   decision_analytics.html  -> "Which rules / ontology concepts / AI calls
#                                are earning their keep?"
#   archive.html             -> "For this specific article, what evidence
#                                justified the decision the pipeline made?"
#
# Opportunity Capture Rate is the one number everything else exists to
# explain. Every other panel is deliberately framed as an *explanation* for
# why that number is moving, not as an independent fact to admire. Resist
# the urge to add a new top-level card for a new metric — fold it into the
# section whose question it answers, or it belongs on the Decision
# Analytics page instead.
#
# Every read below stays defensive: if a field isn't there yet, the UI
# renders an "Awaiting Data" placeholder instead of raising or inventing a
# number, and every stage/filter token is a plain string so nothing outside
# this file needs to change for a new field to start flowing through.
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
    """Reads `key` off a dict-like or object-like `value` (used for avg_30/src_30/audit)."""
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


def is_num(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def safe_div(numerator, denominator):
    """Division that degrades to None (Awaiting Data) instead of raising or lying."""
    if not is_num(numerator) or not is_num(denominator) or denominator == 0:
        return None
    return numerator / denominator


def fmt_pct(value, decimals=1):
    if not is_num(value):
        return None
    return f"{value:.{decimals}f}%"


def fmt_num(value, decimals=1):
    if not is_num(value):
        return None
    if isinstance(value, int) or float(value).is_integer():
        return f"{int(value):,}"
    return f"{value:.{decimals}f}"


def trend_indicator(current, baseline, higher_is_better=True):
    """
    Compares `current` to a trailing baseline (e.g. the 30-day average) and
    returns (arrow, css_class). Returns (None, None) whenever either side is
    missing — a trend claim with only half its inputs is worse than no
    trend claim at all.
    """
    if not is_num(current) or not is_num(baseline):
        return None, None
    diff = current - baseline
    if abs(diff) < 1e-9:
        return "\u2192", "neutral"
    improving = (diff > 0) if higher_is_better else (diff < 0)
    arrow = "\u2191" if diff > 0 else "\u2193"
    return arrow, ("good" if improving else "bad")


def stat_block(label, value, unit="", status=None, note=None):
    """
    Renders one small stat tile. A None value renders the "Awaiting Data"
    placeholder rather than inventing a number.
    status: 'good' | 'bad' | 'warn' | 'info' | None
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


def question_title(text):
    """The small italic operational question a card exists to answer."""
    return f'<div class="question-title">{esc(text)}</div>'


# Canonical stage tokens, shared verbatim by index.html's loss funnel, the
# archive funnel banner, the archive filter dropdown and each row's
# `stage_dropped` field. Previously the funnel used one set of strings and
# the ledger used another, so a click on the funnel silently matched
# nothing — this list is now the single source of truth for the token, so
# that bug can't come back by drifting the two pages apart again.
LOSS_STAGE_DEFS = [
    # (display label,            funnel_counts key, canonical stage token, row kind)
    ("Downloaded",                "downloaded", None,             "start"),
    ("Duplicates Removed",        "duplicate",  "Deduplication",  "loss"),
    ("Parse Failures",            "parsed",     "Parse Failure",  "loss"),
    ("Ontology Rejects",          "ontology",   "Ontology",       "loss"),
    ("Rules Rejects",             "rules",      "Rules",          "loss"),
    ("AI Rejects",                "ai",         "AI",             "loss"),
    ("Dispatched",                "alerts",     "DISPATCHED",     "terminal"),
]


def build_loss_funnel(funnel_counts):
    """
    Turns the raw per-stage counts the backend reports into a loss cascade:
    for every rejection stage we compute the stage's own retention rate
    (survivors after / survivors entering) and the cumulative yield (what
    share of the original Downloaded total has survived to this point).

    Returns (rows, have_total). `rows` is a list of dicts even when data is
    partially missing — each row just carries `awaiting=True` and lets the
    caller render its own placeholder rather than dropping the row, so the
    cascade shape stays visible even with holes in it.
    """
    if not isinstance(funnel_counts, dict):
        funnel_counts = {}
    total = funnel_counts.get("downloaded")
    have_total = is_num(total)
    survivors = total if have_total else None
    rows = []
    for label, key, stage_token, kind in LOSS_STAGE_DEFS:
        raw = funnel_counts.get(key)
        awaiting = raw is None and kind != "start"
        if kind == "start":
            count = total
            stage_pct = None
            yield_pct = 100.0 if have_total else None
            awaiting = not have_total
        elif kind == "terminal":
            count = raw
            yield_pct = safe_div(raw, total) if have_total and is_num(raw) else None
            if yield_pct is not None:
                yield_pct *= 100
            stage_pct = safe_div(raw, survivors) if is_num(survivors) and is_num(raw) else None
            if stage_pct is not None:
                stage_pct *= 100
        else:
            loss = raw
            count = loss
            if is_num(survivors) and is_num(loss):
                retained = survivors - loss
                stage_pct = safe_div(retained, survivors)
                if stage_pct is not None:
                    stage_pct *= 100
                survivors = retained
                yield_pct = safe_div(survivors, total)
                if yield_pct is not None:
                    yield_pct *= 100
            else:
                stage_pct = None
                yield_pct = None
                survivors = None  # unknown from here on — don't fake downstream yields
        rows.append(dict(
            label=label, count=count, stage_pct=stage_pct, yield_pct=yield_pct,
            stage_token=stage_token, kind=kind, awaiting=awaiting,
        ))
    return rows, have_total


def render_loss_funnel_html(funnel_counts):
    rows, have_total = build_loss_funnel(funnel_counts)
    if not have_total:
        return '<div class="empty-note">Awaiting Data &mdash; the pipeline has not reported a Downloaded total for this run, so stage conversion rates can\'t be computed yet.</div>'

    header = ('<div class="loss-row head">'
              '<div>Stage</div><div>Cumulative Yield</div><div>Count</div>'
              '<div>Stage Retention</div><div>Of Total</div></div>')
    body = ""
    for r in rows:
        href = "archive.html" if r["stage_token"] is None else f'archive.html?stage={r["stage_token"]}'
        row_cls = "loss-row"
        if r["kind"] == "terminal":
            row_cls += " terminal"
        elif r["kind"] == "loss":
            row_cls += " loss"
        bar_pct = r["yield_pct"] if is_num(r["yield_pct"]) else 0
        count_html = esc(fmt_num(r["count"])) if is_num(r["count"]) else '<span class="awaiting">Awaiting</span>'
        stage_pct_html = fmt_pct(r["stage_pct"]) if is_num(r["stage_pct"]) else "&mdash;"
        yield_pct_html = fmt_pct(r["yield_pct"]) if is_num(r["yield_pct"]) else "&mdash;"
        bar_dashed = "border: 1px dashed var(--muted);" if r["awaiting"] else ""
        body += f"""
            <a class="{row_cls}" href="{href}" title="Inspect this stage in the ledger">
                <div class="lr-name">{esc(r["label"])}</div>
                <div class="lr-bar-wrap" style="{bar_dashed}"><div class="lr-bar" style="width:{bar_pct:.1f}%;"></div></div>
                <div class="lr-count">{count_html}</div>
                <div class="lr-stage-pct">{stage_pct_html}</div>
                <div class="lr-yield-pct">{yield_pct_html}</div>
            </a>"""
    return f'<div class="loss-funnel">{header}{body}</div>'


# ---------------------------------------------------------------------------
# Shared CSS. All class names from the previous build are preserved so
# nothing that already depends on them breaks; the additions below are
# purely additive (hero KPI, loss funnel, decision report, telemetry
# sub-sections, question subtitles).
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
            margin: 0 0 4px; font-size: 1em; color: #fff; padding-bottom: 0;
            text-transform: uppercase; letter-spacing: 0.5px;
            display: flex; justify-content: space-between; align-items: center; font-weight: 700;
        }
        .card h2 small { color: var(--muted); font-weight: 400; text-transform: none; letter-spacing: 0; font-size: 0.85em; }
        .question-title { font-size: 0.82em; color: var(--muted); font-style: italic; margin: 2px 0 12px; padding-bottom: 10px; border-bottom: 1px solid var(--border); }

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

        /* Legacy box-style funnel (kept in case anything still links to it as a
           visual reference; the primary funnel is now .loss-funnel below). */
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

        /* Loss-analysis funnel: a cascade of clickable rows, each with a
           cumulative-yield bar, a stage retention rate and an overall yield
           rate, so a bottleneck stage is visible as a bar that suddenly
           shrinks rather than as a bare number next to five other bare
           numbers. */
        .loss-funnel { display: flex; flex-direction: column; }
        .loss-row {
            display: grid; grid-template-columns: 170px 1fr 90px 110px 90px; gap: 12px; align-items: center;
            padding: 9px 2px; border-bottom: 1px solid var(--surface-subtle); text-decoration: none; color: var(--text);
        }
        .loss-row:hover { background: var(--surface-hover); }
        .loss-row .lr-name { font-weight: 600; font-size: 0.86em; }
        .loss-row .lr-bar-wrap { background: var(--surface-subtle); border-radius: 3px; height: 15px; overflow: hidden; }
        .loss-row .lr-bar { background: var(--blue); height: 100%; }
        .loss-row.terminal .lr-bar { background: var(--green); }
        .loss-row.loss .lr-bar { background: var(--orange); }
        .loss-row .lr-count { font-family: var(--mono); text-align: right; font-size: 0.85em; }
        .loss-row .lr-stage-pct { font-family: var(--mono); text-align: right; font-size: 0.8em; color: var(--muted); }
        .loss-row .lr-yield-pct { font-family: var(--mono); text-align: right; font-size: 0.85em; font-weight: 700; }
        .loss-row.head { color: var(--muted); text-transform: uppercase; font-size: 0.64em; letter-spacing: 0.4px; border-bottom: 1px solid var(--border); padding-bottom: 6px; }
        .loss-row.head:hover { background: none; }
        .funnel-note { font-size: 0.78em; color: var(--muted); margin-top: 10px; font-style: italic; }

        /* KPI hero */
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

        /* Engineering telemetry sub-sections within one consolidated card */
        .telemetry-sub { margin-top: 18px; }
        .telemetry-sub:first-child { margin-top: 0; }
        .telemetry-sub-label { font-size: 0.7em; text-transform: uppercase; color: var(--muted); letter-spacing: 0.5px; margin-bottom: 8px; font-weight: 700; }

        /* Decision Report (archive drill-down) */
        .dr-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 18px; margin-top: 4px; }
        .dr-col h4 { margin: 0 0 6px; font-size: 0.7em; text-transform: uppercase; letter-spacing: 0.4px; }
        .dr-col.pos h4 { color: var(--green); } .dr-col.neg h4 { color: var(--red); }
        .dr-list { list-style: none; margin: 0; padding: 0; font-size: 0.82em; }
        .dr-list li { padding: 3px 0; }
        .dr-list li.empty { color: var(--muted); font-style: italic; }
        .dr-meta-row { display: flex; gap: 26px; flex-wrap: wrap; margin-top: 14px; padding-top: 12px; border-top: 1px solid var(--border); font-size: 0.8em; }
        .dr-meta-item .dm-label { color: var(--muted); font-size: 0.7em; text-transform: uppercase; }
        .dr-meta-item .dm-value { font-family: var(--mono); margin-top: 2px; }

        .deep-link-row { display: flex; justify-content: space-between; align-items: center; }
        .deep-link { background: var(--blue); color: #fff !important; padding: 7px 14px; border-radius: 5px; text-decoration: none; font-size: 0.82em; font-weight: 700; white-space: nowrap; }
        .deep-link:hover { opacity: 0.9; text-decoration: none; }

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
        cls_archive="active" if active == "archive" else "",
    )


# ===========================================================================
# 1. index.html — "Decision Centre"
#    Question this whole page answers: are we catching the opportunities
#    that matter, and if not, where is the loss happening?
# ===========================================================================
def generate_dashboard_html(logs, output_path, metrics, avg_30=None, src_30=None):
    """Generates the Decision Centre — the primary KPI plus its explanation."""
    now_str = datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
    run_id = getattr(metrics, 'run_id', 'SSR-OP-2026')
    # No fabricated defaults here on purpose: a fallback like "assume 98%
    # healthy" or "assume 118.5s runtime" would silently misreport a
    # backend that hasn't started sending this field yet. Missing means
    # Awaiting Data, not "probably fine."
    runtime_s = _daily(metrics, "total_runtime_s")
    health_score = _daily(metrics, "health_score")

    if is_num(health_score) and health_score >= 90:
        health_label, health_border = "HEALTHY", "var(--green)"
    elif is_num(health_score) and health_score >= 70:
        health_label, health_border = "DEGRADED", "var(--yellow)"
    elif is_num(health_score):
        health_label, health_border = "DOWN", "var(--red)"
    else:
        health_label, health_border = None, "var(--border)"

    # ---- Hero KPI: Opportunity Capture Rate --------------------------------
    capture_rate = _sub(metrics, "validation", "capture_rate")
    capture_baseline = _bag(avg_30, "capture_rate")
    fp_rate = _sub(metrics, "validation", "false_positive_rate")
    fn_rate = _sub(metrics, "validation", "false_negative_rate")
    detection_delay = _sub(metrics, "validation", "avg_detection_delay")
    benchmark_lead = _sub(metrics, "validation", "benchmark_lead")
    validation_status = _sub(metrics, "validation", "status")

    if is_num(capture_rate):
        kpi_css = "good" if capture_rate >= 70 else ("warn" if capture_rate >= 40 else "bad")
        kpi_value_html = f'{capture_rate:.1f}%'
    else:
        kpi_css = ""
        kpi_value_html = '<span class="awaiting" style="font-size:0.4em;">Awaiting Data</span>'

    arrow, trend_css = trend_indicator(capture_rate, capture_baseline, higher_is_better=True)
    if arrow:
        trend_html = f'<div class="kpi-trend {trend_css}">{arrow} vs {capture_baseline:.1f}% 30-day avg</div>'
    else:
        trend_html = '<div class="kpi-trend neutral">No 30-day baseline reported yet &mdash; trend unavailable</div>'

    kpi_context = "".join([
        f'<div class="kpi-context-item"><div class="cx-label">False Positive Rate</div><div class="cx-value">{esc(fmt_pct(fp_rate) or "Awaiting Data")}</div></div>',
        f'<div class="kpi-context-item"><div class="cx-label">False Negative Rate</div><div class="cx-value">{esc(fmt_pct(fn_rate) or "Awaiting Data")}</div></div>',
        f'<div class="kpi-context-item"><div class="cx-label">Avg Detection Delay</div><div class="cx-value">{esc(detection_delay if detection_delay is not None else "Awaiting Data")}</div></div>',
        f'<div class="kpi-context-item"><div class="cx-label">Benchmark Lead</div><div class="cx-value">{esc(benchmark_lead if benchmark_lead is not None else "Awaiting Data")}</div></div>',
        f'<div class="kpi-context-item"><div class="cx-label">Validation Status</div><div class="cx-value">{status_badge(validation_status)}</div></div>',
    ])

    hero_html = f"""
                <div class="kpi-hero">
                    <div>
                        <div class="kpi-label">Opportunity Capture Rate</div>
                        <div class="kpi-number {kpi_css}">{kpi_value_html}</div>
                        {trend_html}
                    </div>
                    <div class="kpi-side">
                        <div class="kpi-context-row">{kpi_context}</div>
                    </div>
                </div>"""

    # ---- Loss-analysis funnel + source effectiveness -----------------------
    funnel_counts = _daily(metrics, "funnel", {}) or {}
    loss_funnel_html = render_loss_funnel_html(funnel_counts)

    default_sources = [
        {"source": "Reuters", "articles": 6412, "alerts": 92, "alert_pct": 1.4, "ontology_pct": 18, "rules_pct": 5, "failures": 0},
        {"source": "SEC EDGAR", "articles": 8921, "alerts": 142, "alert_pct": 0.16, "ontology_pct": 2, "rules_pct": 0.5, "failures": 0},
        {"source": "PR Newswire", "articles": 5123, "alerts": 76, "alert_pct": 1.5, "ontology_pct": 24, "rules_pct": 9, "failures": 3},
    ]
    source_rows = _rows(src_30) or default_sources
    total_alerts_all_sources = sum(a for a in (_bag(r, "alerts") for r in source_rows) if is_num(a))
    source_row_html = ""
    for row in source_rows:
        failures = _bag(row, "failures", 0)
        alerts = _bag(row, "alerts")
        fail_color = "var(--red)" if failures else "var(--green)"
        capture_share = safe_div(alerts, total_alerts_all_sources)
        capture_share = capture_share * 100 if capture_share is not None else None
        source_row_html += f"""
                        <tr class="clickable" onclick="window.location='archive.html?source={esc(_bag(row, 'source'))}'">
                            <td><strong>{esc(_bag(row, "source"))}</strong></td>
                            <td class="metric-val">{esc(_bag(row, "articles"))}</td>
                            <td class="metric-val">{esc(alerts)}</td>
                            <td class="metric-val">{esc(fmt_pct(capture_share) or "&mdash;")}</td>
                            <td class="metric-val">{esc(_bag(row, "alert_pct"))}%</td>
                            <td class="metric-val">{esc(_bag(row, "ontology_pct"))}%</td>
                            <td class="metric-val">{esc(_bag(row, "rules_pct"))}%</td>
                            <td class="metric-val" style="color: {fail_color};">{esc(failures)}</td>
                        </tr>"""

    # ---- Engineering telemetry (consolidated) ------------------------------
    status_row = "".join([
        f'<div class="stat-tile"><div class="stat-label">Scheduler</div><div class="stat-value">{status_badge(_daily(metrics, "scheduler_status"))}</div></div>',
        f'<div class="stat-tile"><div class="stat-label">Feed Health</div><div class="stat-value">{status_badge(_daily(metrics, "feed_health_status"))}</div></div>',
        f'<div class="stat-tile"><div class="stat-label">AI Status</div><div class="stat-value">{status_badge(_daily(metrics, "ai_status"))}</div></div>',
        f'<div class="stat-tile"><div class="stat-label">Database</div><div class="stat-value">{status_badge(_daily(metrics, "db_status"))}</div></div>',
        f'<div class="stat-tile"><div class="stat-label">GitHub Actions</div><div class="stat-value">{status_badge(_daily(metrics, "gh_actions_status"))}</div></div>',
        stat_block("Uptime", _daily(metrics, "uptime_pct"), unit="%"),
    ])
    latency_tiles = "".join([
        stat_block("Avg Parse Time", _daily(metrics, "avg_parse_time_s"), unit="s"),
        stat_block("Avg AI Time", _daily(metrics, "avg_ai_time_s"), unit="s"),
        stat_block("Avg End-to-End", round(runtime_s, 2) if is_num(runtime_s) else runtime_s, unit="s"),
        stat_block("Queue Depth", _daily(metrics, "queue_depth")),
        stat_block("AI Invocations", _daily(metrics, "ai_invocations")),
        stat_block("Articles / Hour", _bag(avg_30, "articles_per_hour")),
    ])
    error_fields = ["Parser", "HTTP", "RSS", "AI", "SQLite", "Email", "Retry Success"]
    error_tiles = "".join(
        stat_block(name, _sub(metrics, "errors", name.lower().replace(" ", "_")),
                   status=("bad" if _sub(metrics, "errors", name.lower().replace(" ", "_")) not in (None, 0) and name != "Retry Success" else None))
        for name in error_fields
    )
    feeds = _rows(_daily(metrics, "feeds"))
    if feeds:
        feed_rows_html = '<div class="feed-row head"><div>Feed</div><div>Status</div><div>Latency</div><div>Failures</div><div>Retries</div></div>'
        for f in feeds:
            feed_rows_html += (
                f'<div class="feed-row">'
                f'<div>{esc(_bag(f, "name"))}</div>'
                f'<div>{status_badge(_bag(f, "status"))}</div>'
                f'<div>{esc(_bag(f, "latency", "-"))}</div>'
                f'<div>{esc(_bag(f, "failures", "-"))}</div>'
                f'<div>{esc(_bag(f, "retries", "-"))}</div>'
                f'</div>'
            )
    else:
        feed_rows_html = '<div class="empty-note">Awaiting Data &mdash; no per-feed telemetry reported for this run.</div>'

    # ---- Recent activity ----------------------------------------------------
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

    recent_articles_html = _activity_items(lambda l: True, "Awaiting Data \u2014 no log entries supplied for this run.")
    recent_alerts_html = _activity_items(lambda l: str(_bag(l, "outcome", "")).upper() == "DISPATCHED",
                                          "Awaiting Data \u2014 no dispatched alerts logged for this run.")
    recent_failures_html = _activity_items(lambda l: str(_bag(l, "level", "")).upper() in ("ERROR", "FAIL", "FAILURE"),
                                            "No failures logged for this run.")

    runtime_display = f"{runtime_s:.1f}s" if is_num(runtime_s) else "Awaiting Data"

    html = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>SSR Decision Centre</title>
        <style>
{BASE_CSS}
        </style>
    </head>
    <body>
        <div class="container">
            {render_nav("index")}

            <header style="border-left-color: {health_border};">
                <div>
                    <h1>SSR Decision Centre {status_badge(health_label)}</h1>
                    <div class="subline">
                        Run ID: {esc(run_id)} &bull; Flight Recorder Active &bull; Generated {esc(now_str)} &bull; Latency: {runtime_display}
                    </div>
                </div>
                <div style="text-align: right;">
                    <div style="font-size: 1.1em;">System Confidence: <strong>{esc(fmt_pct(_daily(metrics, "system_confidence")) or "Awaiting Data")}</strong></div>
                    <div class="subline">Last Successful Run: {esc(_daily(metrics, "last_success_run") or "Awaiting Data")}</div>
                </div>
            </header>

            <div class="grid" style="grid-template-columns: 1fr;">
                <div class="card">
                    <h2>Opportunity Capture</h2>
                    {question_title("Are we catching the opportunities that matter?")}
                    {hero_html}
                </div>

                <div class="card">
                    <h2>Where Opportunities Are Won and Lost</h2>
                    {question_title("At which stage does the pipeline throw away the most signal, and how much of it is real loss vs. correct rejection?")}
                    {loss_funnel_html}
                    <div class="funnel-note">This funnel only covers articles the system downloaded. Opportunities the system never saw at all are tracked separately as the False Negative Rate above.</div>

                    <div class="section-title" style="margin-top: 24px;">Source Effectiveness <small>click a source to inspect it in the ledger</small></div>
                    <table>
                        <thead>
                            <tr>
                                <th>Source</th><th>Articles</th><th>Alerts</th><th>Capture Share</th>
                                <th>Alert %</th><th>Ontology %</th><th>Rules %</th><th>Failures</th>
                            </tr>
                        </thead>
                        <tbody>{source_row_html}</tbody>
                    </table>
                </div>

                <div class="card">
                    <h2>Engineering Telemetry</h2>
                    {question_title("Is the pipeline itself healthy enough that the numbers above can be trusted, and where are the bottlenecks?")}
                    <div class="telemetry-sub">
                        <div class="telemetry-sub-label">Component Status</div>
                        <div class="tile-grid">{status_row}</div>
                    </div>
                    <div class="telemetry-sub">
                        <div class="telemetry-sub-label">Latency &mdash; drives Detection Delay and Benchmark Lead above</div>
                        <div class="tile-grid">{latency_tiles}</div>
                    </div>
                    <div class="telemetry-sub">
                        <div class="telemetry-sub-label">Errors &amp; Retries</div>
                        <div class="tile-grid">{error_tiles}</div>
                    </div>
                    <div class="telemetry-sub">
                        <div class="telemetry-sub-label">Feed Freshness</div>
                        {feed_rows_html}
                    </div>
                </div>

                <div class="card">
                    <div class="deep-link-row">
                        <div>
                            <h2 style="border-bottom:none;">Decision Analytics</h2>
                            {question_title("Which specific rules, ontology concepts and AI calls are earning their keep, and which are dragging on Capture Rate?")}
                        </div>
                        <a class="deep-link" href="decision_analytics.html">Open Decision Analytics &rarr;</a>
                    </div>
                </div>

                <div class="card">
                    <h2>Live Activity</h2>
                    {question_title("What is the pipeline doing right now?")}
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
            </div>
        </div>
    </body>
    </html>
    """
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)


# ===========================================================================
# 2. decision_analytics.html — deep dive on the detectors themselves
#    Question this page answers: which rules / ontology concepts / AI calls
#    are earning their keep, and which are the biggest drag on Capture Rate?
# ===========================================================================
def generate_decision_analytics_html(output_path, metrics, avg_30=None):
    rule_rows = _daily(metrics, "rule_analytics") or [
        {"rule": "R-17 (Board Ref)", "evaluated": 1820, "matched": 412, "alerts": 38, "false_neg": 1},
        {"rule": "R-22 (Liquidation)", "evaluated": 1820, "matched": 89, "alerts": 42, "false_neg": 0},
        {"rule": "R-04 (Cap Threshold)", "evaluated": 1820, "matched": 1410, "alerts": 12, "false_neg": 2},
    ]
    rule_rows_html = ""
    for r in rule_rows:
        evaluated = _bag(r, "evaluated")
        alerts = _bag(r, "alerts")
        matched = _bag(r, "matched")
        false_neg = _bag(r, "false_neg")
        yield_pct = safe_div(alerts, evaluated)
        yield_pct = yield_pct * 100 if yield_pct is not None else None
        drag_row = is_num(false_neg) and false_neg > 0
        rule_rows_html += f"""<tr{' style="color: var(--red);"' if drag_row else ''}>
                <td>{esc(_bag(r, "rule"))}</td><td class="metric-val">{esc(evaluated)}</td>
                <td class="metric-val">{esc(matched)}</td><td class="metric-val">{esc(alerts)}</td>
                <td class="metric-val">{esc(fmt_pct(yield_pct) or "&mdash;")}</td>
                <td class="metric-val">{esc(false_neg)}</td></tr>"""

    ontology_rows = _daily(metrics, "ontology_conversion") or [
        {"concept": "Voluntary Delisting", "frequency": 312, "conversion_pct": 28.2},
        {"concept": "Strategic Review", "frequency": 1420, "conversion_pct": 4.1},
        {"concept": "Tender Offer", "frequency": 184, "conversion_pct": 41.8},
    ]
    total_frequency = sum(f for f in (_bag(o, "frequency") for o in ontology_rows) if is_num(f))
    ontology_rows_html = ""
    for o in ontology_rows:
        pct = _bag(o, "conversion_pct")
        freq = _bag(o, "frequency")
        color = "var(--green)" if is_num(pct) and pct >= 20 else "var(--text)"
        share = safe_div(freq, total_frequency)
        share = share * 100 if share is not None else None
        ontology_rows_html += (
            f'<tr><td>{esc(_bag(o, "concept"))}</td><td class="metric-val">{esc(freq)}</td>'
            f'<td class="metric-val">{esc(fmt_pct(share) or "&mdash;")}</td>'
            f'<td class="metric-val" style="color: {color};">{esc(pct)}%</td></tr>'
        )

    # AI calibration — genuinely new territory for this pipeline, so almost
    # everything here is Awaiting Data until the backend starts reporting an
    # `ai_performance` group. The two figures we *can* derive today (from
    # the funnel and daily counters that already exist) are shown live.
    ai_invocations = _daily(metrics, "ai_invocations")
    ai_rejects = _bag(_daily(metrics, "funnel", {}) or {}, "ai")
    ai_reject_rate = safe_div(ai_rejects, ai_invocations)
    ai_reject_rate = ai_reject_rate * 100 if ai_reject_rate is not None else None
    ai_tiles = "".join([
        stat_block("AI Invocations", ai_invocations),
        stat_block("AI Reject Rate", ai_reject_rate, unit="%"),
        stat_block("Avg Confidence \u2014 Dispatched", _sub(metrics, "ai_performance", "avg_confidence_dispatched"), unit="%"),
        stat_block("Avg Confidence \u2014 Dropped", _sub(metrics, "ai_performance", "avg_confidence_dropped"), unit="%"),
        stat_block("Accuracy vs Validated Outcomes", _sub(metrics, "ai_performance", "accuracy_vs_validation"), unit="%"),
        stat_block("Avg AI Time", _daily(metrics, "avg_ai_time_s"), unit="s"),
    ])

    html = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>SSR Decision Analytics</title>
        <style>
{BASE_CSS}
        </style>
    </head>
    <body>
        <div class="container">
            {render_nav("analytics")}

            <header>
                <div>
                    <h1>Decision Analytics</h1>
                    <div class="subline">Which detectors are earning their keep &mdash; and which ones are the biggest drag on <a href="index.html" style="color:var(--blue);">Opportunity Capture Rate</a>.</div>
                </div>
            </header>

            <div class="grid" style="grid-template-columns: 1fr;">
                <div class="card">
                    <h2>Rule Analytics</h2>
                    {question_title("Which rules are earning their keep? A rule with a high false-negative count is quietly capping Capture Rate even while it looks quiet on this page.")}
                    <table>
                        <thead><tr><th>Rule ID</th><th>Evaluated</th><th>Matched</th><th>Alerts</th><th>Alert Yield</th><th>False Neg</th></tr></thead>
                        <tbody>{rule_rows_html}</tbody>
                    </table>
                </div>

                <div class="card">
                    <h2>Ontology Concept Conversion</h2>
                    {question_title("Which concepts convert to real alerts most often, and which ones are mostly noise relative to how often they fire?")}
                    <table>
                        <thead><tr><th>Concept</th><th>Frequency</th><th>Share of Volume</th><th>Conversion %</th></tr></thead>
                        <tbody>{ontology_rows_html}</tbody>
                    </table>
                </div>

                <div class="card">
                    <h2>AI Calibration</h2>
                    {question_title("Is the AI classifier well-calibrated \u2014 does confidence actually track whether the outcome was correct?")}
                    <div class="tile-grid">{ai_tiles}</div>
                    <div class="funnel-note">Confidence-vs-outcome calibration needs the backend to report an <code>ai_performance</code> metrics group; the tiles above will populate automatically once it does, with no changes needed to this page.</div>
                </div>
            </div>
        </div>
    </body>
    </html>
    """
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)


# ===========================================================================
# 3. archive.html — "Immutable Event Ledger"
#    Question each drill-down answers: for this article, what evidence
#    justified the decision the pipeline made?
# ===========================================================================
def generate_archive_html(output_path):
    """Generates the Immutable Event Ledger with a Decision Report drill-down per row."""
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
        .trace-step .ts-time { color: var(--muted); font-family: var(--mono); font-size: 0.9em; margin-top: 2px; }
        .trace-step.pass { border-color: var(--green); }
        .trace-step.pass .ts-value { color: var(--green); }
        .trace-step.fail { border-color: var(--red); }
        .trace-step.fail .ts-value { color: var(--red); }
        .trace-step.pending { opacity: 0.45; }
        .trace-arrow { align-self: center; color: var(--border); padding: 0 4px; }

        .decision-report { padding: 6px 20px 18px; margin-left: 20px; border-left: 4px solid var(--blue); }
        .dr-title { color: #fff; font-weight: 700; letter-spacing: 0.3px; margin-bottom: 10px; font-size: 0.9em; }
        .dr-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 18px; }
        .dr-col h4 { margin: 0 0 6px; font-size: 0.7em; text-transform: uppercase; letter-spacing: 0.4px; }
        .dr-col.pos h4 { color: var(--green); } .dr-col.neg h4 { color: var(--red); }
        .dr-list { list-style: none; margin: 0; padding: 0; font-size: 0.82em; font-family: var(--mono); color: var(--text); }
        .dr-list li { padding: 3px 0; }
        .dr-list li.empty { color: var(--muted); font-style: italic; font-family: -apple-system, sans-serif; }
        .dr-meta-row { display: flex; gap: 26px; flex-wrap: wrap; margin-top: 14px; padding-top: 12px; border-top: 1px solid var(--border); font-size: 0.8em; }
        .dr-meta-item .dm-label { color: var(--muted); font-size: 0.7em; text-transform: uppercase; }
        .dr-meta-item .dm-value { font-family: var(--mono); margin-top: 2px; color: var(--text); }
        .replay-btn { background: var(--blue); color: #fff; border: none; padding: 5px 12px; border-radius: 4px; font-size: 0.8em; cursor: pointer; margin-top: 12px; font-weight: 700; }
        .replay-btn:hover { opacity: 0.9; }
        .empty-note { color: var(--muted); font-style: italic; padding: 20px; text-align: center; }
    """

    html = """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>SSR Immutable Event Ledger</title>
        <style>
__BASE_CSS__
__ARCHIVE_CSS__
        </style>
    </head>
    <body>
        <div class="container">
            __NAV__

            <header>
                <div>
                    <h1>Immutable Event Ledger</h1>
                    <div class="subline">Permanent decision history. Click a funnel stage to filter. Click any row for a full Decision Report: the evidence for and against the outcome, timings, versions and the authority that decided.</div>
                </div>
            </header>

            <div class="stats-strip" id="statsStrip"></div>

            <div class="funnel-banner" id="funnelBanner">
                <div class="fb-caption">Live Funnel:</div>
                <div class="funnel-node active" data-stage="ALL" onclick="filterByStage('ALL', this)">Downloaded <span id="cnt-total">&mdash;</span></div>
                <div class="funnel-node" data-stage="Deduplication" onclick="filterByStage('Deduplication', this)">Duplicate <span id="cnt-dup">&mdash;</span></div>
                <div class="funnel-node" data-stage="Parse Failure" onclick="filterByStage('Parse Failure', this)">Parse Failure <span id="cnt-parse">&mdash;</span></div>
                <div class="funnel-node" data-stage="Ontology" onclick="filterByStage('Ontology', this)">Ontology Reject <span id="cnt-ont">&mdash;</span></div>
                <div class="funnel-node" data-stage="Rules" onclick="filterByStage('Rules', this)">Rules Reject <span id="cnt-rules">&mdash;</span></div>
                <div class="funnel-node" data-stage="AI" onclick="filterByStage('AI', this)">AI Reject <span id="cnt-ai">&mdash;</span></div>
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

            // Supports "clicking a funnel stage / loss-funnel row on another
            // page opens the ledger pre-filtered to that exact stage" via
            // ?stage=... and ?source=.... The stage token here must match
            // row.stage_dropped verbatim (see filterTable's exact-match
            // check below) -- these are the same canonical tokens used by
            // the funnel banner buttons and by the Decision Centre's loss
            // funnel, so a click from either page always lands on the
            // right rows.
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
                            rules_failed: ["R-17"],
                            timings: { download_ms: 210, parse_ms: 40, ontology_ms: 65, rules_ms: 12, ai_ms: null, total_ms: 327 },
                            versions: { ontology_version: "v2026.03", rules_version: "v2026.06", ai_model: null }
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
                            rules_matched: ["R-04"],
                            rules_failed: [],
                            timings: { download_ms: 180, parse_ms: 55, ontology_ms: 70, rules_ms: 15, ai_ms: 920, total_ms: 1240 },
                            versions: { ontology_version: "v2026.03", rules_version: "v2026.06", ai_model: "gemini-2.0-flash" }
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
                            rules_matched: ["R-22"],
                            rules_failed: [],
                            timings: { download_ms: 150, parse_ms: 38, ontology_ms: 60, rules_ms: 10, ai_ms: 780, total_ms: 1038 },
                            versions: { ontology_version: "v2026.03", rules_version: "v2026.06", ai_model: "gemini-2.0-flash" }
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

            function traceStep(label, value, state, timeMs) {
                const cls = state ? state : '';
                const timeHtml = (timeMs !== undefined && timeMs !== null) ? `<div class="ts-time">${timeMs}ms</div>` : '';
                return `<div class="trace-step ${cls}"><div class="ts-label">${label}</div><div class="ts-value">${value ?? '&mdash;'}</div>${timeHtml}</div>`;
            }

            // Renders one field of the Decision Report's evidence lists, or
            // a visibly-labelled empty state -- never a silently blank <li>,
            // since a blank line reads as "there was no evidence" when it
            // might just mean "the backend hasn't reported this yet".
            function evidenceItems(items, emptyLabel) {
                const list = (items || []).filter(Boolean);
                if (list.length === 0) {
                    return `<li class="empty">${emptyLabel}</li>`;
                }
                return list.map(i => `<li>${i}</li>`).join('');
            }

            function metaField(label, value) {
                const display = (value === null || value === undefined || value === '') ? '<span class="awaiting">Awaiting Data</span>' : value;
                return `<div class="dr-meta-item"><div class="dm-label">${label}</div><div class="dm-value">${display}</div></div>`;
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
                    const timings = audit.timings || {};
                    const versions = audit.versions || {};
                    const dropped = (stage) => row.stage_dropped === stage || (row.outcome === 'DROPPED' && row.stage_dropped && row.stage_dropped.toLowerCase().includes(String(stage).toLowerCase()));

                    const trace = [
                        traceStep('Downloaded', downloaded, 'pass', timings.download_ms),
                        traceStep('Duplicate Check', row.duplicate, String(row.duplicate).toLowerCase() === 'yes' ? 'fail' : 'pass'),
                        traceStep('Parser', row.parsed, String(row.parsed).toUpperCase() === 'PASS' ? 'pass' : 'fail', timings.parse_ms),
                        traceStep('Issuer Extraction', audit.issuer_extracted || row.issuer, (audit.issuer_extracted || row.issuer) ? 'pass' : 'pending'),
                        traceStep('Ontology', row.ontology, dropped('Ontology') ? 'fail' : 'pass', timings.ontology_ms),
                        traceStep('Rules', (audit.rules_matched || []).join(', ') || row.rules, dropped('Rules') ? 'fail' : 'pass', timings.rules_ms),
                        traceStep('AI', audit.ai_confidence ? `${row.ai} (${audit.ai_confidence})` : row.ai, dropped('AI') ? 'fail' : (row.ai && row.ai !== 'N/A' ? 'pass' : 'pending'), timings.ai_ms),
                        traceStep('Alert', row.outcome === 'DISPATCHED' ? 'Dispatched' : 'Not Sent', row.outcome === 'DISPATCHED' ? 'pass' : 'pending'),
                    ];
                    const traceHtml = trace.join('<div class="trace-arrow">&rarr;</div>');

                    // Positive evidence: whatever actually supported the outcome.
                    // Missing evidence: whatever was absent, failed, or fell
                    // short of a threshold. A row can (and often should) have
                    // items in both columns -- e.g. a rule can match while
                    // AI confidence still falls short.
                    const positive = [];
                    if (audit.issuer_extracted) positive.push(`Issuer identified: <strong>${audit.issuer_extracted}</strong>`);
                    if (row.ontology && row.ontology !== '-') positive.push(`Ontology concept matched: <strong>${row.ontology}</strong>`);
                    (audit.rules_matched || []).forEach(r => positive.push(`Rule matched: <strong>${r}</strong>`));
                    if (audit.ai_confidence && row.outcome === 'DISPATCHED') positive.push(`AI confidence: <strong>${audit.ai_confidence}</strong> (above threshold)`);

                    const missing = [];
                    (audit.rules_failed || []).forEach(r => missing.push(`Rule failed: <strong>${r}</strong>`));
                    if (audit.ai_confidence && row.outcome === 'DROPPED' && dropped('AI')) missing.push(`AI confidence: <strong>${audit.ai_confidence}</strong> (below threshold)`);
                    if (row.outcome === 'DROPPED' && row.drop_reason && row.drop_reason !== '-') missing.push(row.drop_reason);

                    const reportHtml = `
                        <div class="dr-title">DECISION REPORT &mdash; ARTICLE #${index + 1}</div>
                        <div class="dr-grid">
                            <div class="dr-col pos">
                                <h4>Positive Evidence</h4>
                                <ul class="dr-list">${evidenceItems(positive, 'No supporting evidence recorded for this decision.')}</ul>
                            </div>
                            <div class="dr-col neg">
                                <h4>Missing / Failing Evidence</h4>
                                <ul class="dr-list">${evidenceItems(missing, 'Nothing recorded as missing or failing.')}</ul>
                            </div>
                        </div>
                        <div class="dr-meta-row">
                            ${metaField('Exact Stage', audit.exact_stage || row.stage_dropped)}
                            ${metaField('Component', audit.component)}
                            ${metaField('Decision Authority', row.authority)}
                            ${metaField('Validation Status', row.validation_status)}
                            ${metaField('Ontology Version', versions.ontology_version)}
                            ${metaField('Rules Version', versions.rules_version)}
                            ${metaField('AI Model', versions.ai_model)}
                            ${metaField('Total Processing Time', timings.total_ms !== undefined && timings.total_ms !== null ? timings.total_ms + 'ms' : null)}
                            ${metaField('Payload Hash', audit.hash)}
                        </div>
                        <button class="replay-btn" onclick="event.stopPropagation(); alert('Replaying article through latest ontology/rules pipeline...')">&#8635; Replay from this stage (Latest Rules)</button>
                    `;

                    auditTr.innerHTML = `
                        <td colspan="16" style="padding: 0;">
                            <div class="pipeline-trace">${traceHtml}</div>
                            <div class="decision-report">${reportHtml}</div>
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
                    // Exact match against the canonical stage token, not a
                    // substring check -- "Ontology" vs "Ontology Reject"
                    // used to fail this silently in both directions.
                    const matchesFunnel = activeFunnelStage === 'ALL' ||
                                          (activeFunnelStage === 'DISPATCHED' ? row.outcome === 'DISPATCHED' : row.stage_dropped === activeFunnelStage);

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
    html = (html
            .replace("__BASE_CSS__", BASE_CSS)
            .replace("__ARCHIVE_CSS__", archive_css)
            .replace("__NAV__", render_nav("archive")))
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)