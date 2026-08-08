"""Strict contracts shared by source acquisition and the ingestion auditor.

The ingestion boundary is deliberately conservative.  A scraper may return no
articles only when it also records machine-verifiable evidence explaining why
the publication universe was exhausted.  This module is kept free of database
or HTTP dependencies so the same rules are exercised by unit tests and the
live monitor.
"""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime
from hashlib import sha256
from typing import Any, Iterable
from urllib.parse import urlparse


SUCCESS_TERMINATIONS = frozenset(
    {
        "SUCCESS_EXHAUSTED",
        "SUCCESS_CHECKPOINT",
        "SUCCESS_PUBLICATION_WINDOW_REACHED",
    }
)

EXHAUSTION_EVIDENCE_KINDS = frozenset(
    {
        "api_cursor_exhausted",
        "feed_exhausted",
        "pagination_exhausted",
        "checkpoint_reached",
        "publication_window_reached",
    }
)

EMPTY_TITLE_SENTINELS = frozenset({"", "no title", "untitled", "html document"})


def source_name(source: dict[str, Any]) -> str:
    """Return the canonical source name used by the Sources control plane."""
    return str(source.get("Source Name") or source.get("Source") or "Unknown").strip()


def source_url(source: dict[str, Any]) -> str:
    return str(source.get("Target URL") or source.get("URL") or "").strip()


def source_is_enabled(source: dict[str, Any]) -> bool:
    """Accept the boolean spellings used by the Sources Google Sheet."""
    value = source.get("Enabled", source.get("Active", "TRUE"))
    if isinstance(value, bool):
        return value
    return str(value).strip().upper() in {"TRUE", "YES", "Y", "1"}


def new_ledger(source: dict[str, Any], *, adapter: str, channel: str) -> dict[str, Any]:
    """Create a complete, fail-closed per-source ledger entry."""
    return {
        "source": source_name(source),
        "configured_mode": source.get("Type", "Unknown"),
        "configured_url": source_url(source),
        "resolved_adapter": adapter,
        "channel": channel,
        "actual_url": source_url(source),
        "status": "FAILED",
        "health": "DEGRADED",
        "reason": "Scraper did not provide an explicit successful outcome",
        "termination_reason": "UNEXPLAINED_TERMINATION",
        "exhaustion_evidence": None,
        "pagination": {"has_next_page": None},
        "pages_attempted": 0,
        "pages_successful": 0,
        "articles_discovered": 0,
        "articles_emitted": 0,
        "extraction_failures": 0,
        "article_provenance": [],
        "http_statuses": [],
        "waf_events": 0,
        "rate_limit_events": 0,
        "parser_errors": 0,
        "checkpoint_before": None,
        "checkpoint_after": None,
        "checkpoint_found": False,
        "recovery_attempted": False,
        "recovery_status": "NOT_REQUIRED",
        "potential_recall_loss": False,
        "checkpoint_frozen": True,
        "first_publication_timestamp": None,
        "last_publication_timestamp": None,
        # Existing callers still use these names.  They are always timestamps,
        # never URL/id fallbacks.
        "oldest_article_seen": None,
        "newest_article_seen": None,
        "metadata": {},
    }


def _as_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    return value if isinstance(value, list) else [value]


def normalized_http_statuses(metadata: dict[str, Any]) -> list[int]:
    statuses = metadata.get("http_statuses", metadata.get("http_status"))
    result: list[int] = []
    for status in _as_list(statuses):
        try:
            result.append(int(status))
        except (TypeError, ValueError):
            continue
    return result


def normalize_scraper_metadata(ledger: dict[str, Any], metadata: dict[str, Any] | None) -> dict[str, Any]:
    """Copy source metadata into a ledger without granting implicit success.

    Scraper classes historically used many incomplete metadata shapes.  The
    adapter can preserve those diagnostics, but only the strict termination
    contract below can result in a success state.
    """
    meta = deepcopy(metadata or {})
    ledger["metadata"] = meta

    for field in (
        "actual_url",
        "checkpoint_found",
        "recovery_attempted",
        "recovery_status",
        "potential_recall_loss",
        "checkpoint_frozen",
        "reason",
    ):
        if field in meta:
            ledger[field] = meta[field]

    ledger["pages_attempted"] = _as_int(
        meta.get("pages_attempted", meta.get("pages_scanned", meta.get("pages_visited", 0)))
    )
    ledger["pages_successful"] = _as_int(
        meta.get("pages_successful", meta.get("pages_scanned", meta.get("pages_visited", 0)))
    )
    # Compatibility mirrors for existing dashboards / sheet telemetry.
    ledger["pages_scanned"] = ledger["pages_successful"]
    ledger["http_statuses"] = normalized_http_statuses(meta)
    ledger["waf_events"] = _as_int(meta.get("waf_events", 0))
    ledger["rate_limit_events"] = _as_int(meta.get("rate_limit_events", 0))
    ledger["parser_errors"] = _as_int(meta.get("parser_errors", 0))
    if "pagination" in meta and isinstance(meta["pagination"], dict):
        ledger["pagination"] = deepcopy(meta["pagination"])

    ledger["termination_reason"] = str(meta.get("termination_reason") or "UNEXPLAINED_TERMINATION")
    ledger["exhaustion_evidence"] = deepcopy(meta.get("exhaustion_evidence"))
    return ledger


def _evidence_kind(evidence: Any) -> str | None:
    if isinstance(evidence, dict):
        kind = evidence.get("kind")
        return str(kind).strip() if kind else None
    return None


def exhaustion_evidence_is_valid(
    termination_reason: str,
    evidence: Any,
    pagination: dict[str, Any] | None = None,
    *,
    checkpoint_found: bool = False,
) -> bool:
    """Validate the evidence/termination relationship, not just a label."""
    if termination_reason not in SUCCESS_TERMINATIONS or not isinstance(evidence, dict):
        return False
    if evidence.get("verified") is not True:
        return False
    kind = _evidence_kind(evidence)
    if kind not in EXHAUSTION_EVIDENCE_KINDS:
        return False
    if not evidence.get("detail"):
        return False

    pagination = pagination or {}
    # A source may only claim exhaustion if its own pagination signal agrees.
    if pagination.get("has_next_page") is True:
        return False

    if termination_reason == "SUCCESS_EXHAUSTED":
        return kind in {"api_cursor_exhausted", "feed_exhausted", "pagination_exhausted"}
    if termination_reason == "SUCCESS_CHECKPOINT":
        return kind == "checkpoint_reached" and bool(checkpoint_found or evidence.get("checkpoint"))
    if termination_reason == "SUCCESS_PUBLICATION_WINDOW_REACHED":
        return kind == "publication_window_reached" and bool(evidence.get("window"))
    return False


def apply_acquisition_contract(ledger: dict[str, Any]) -> dict[str, Any]:
    """Fail closed when a source's acquisition telemetry is inconsistent."""
    term = str(ledger.get("termination_reason") or "UNEXPLAINED_TERMINATION")
    statuses = ledger.get("http_statuses") or []
    parser_errors = _as_int(ledger.get("parser_errors", 0))
    rate_limits = _as_int(ledger.get("rate_limit_events", 0))
    evidence_valid = exhaustion_evidence_is_valid(
        term,
        ledger.get("exhaustion_evidence"),
        ledger.get("pagination"),
        checkpoint_found=bool(ledger.get("checkpoint_found")),
    )

    # Preserve a concrete transport failure over a potentially stale scraper
    # success value.  These statuses are acceptance failures by definition.
    if 403 in statuses:
        term = "HTTP_403"
    elif 429 in statuses or rate_limits:
        term = "HTTP_429"
    elif any(status >= 400 for status in statuses):
        term = f"HTTP_{next(status for status in statuses if status >= 400)}"
    elif parser_errors:
        term = "PARSER_ERROR"
    elif term in SUCCESS_TERMINATIONS and not evidence_valid:
        term = "UNEXPLAINED_TERMINATION"
    elif term not in SUCCESS_TERMINATIONS:
        # Do not translate old implicit fallbacks such as PAGINATION_EXHAUSTED.
        term = term or "UNEXPLAINED_TERMINATION"

    ledger["termination_reason"] = term
    ledger["exhaustion_evidence_valid"] = evidence_valid and term in SUCCESS_TERMINATIONS
    success = term in SUCCESS_TERMINATIONS and ledger["exhaustion_evidence_valid"]
    ledger["status"] = "OK" if success else "FAILED"
    ledger["health"] = "OK" if success else "DEGRADED"
    ledger["checkpoint_frozen"] = not success
    if not success and not ledger.get("reason"):
        ledger["reason"] = f"Acquisition contract rejected {term}"
    return ledger


def valid_title(value: Any) -> bool:
    return str(value or "").strip().lower() not in EMPTY_TITLE_SENTINELS


def valid_url(value: Any) -> bool:
    parsed = urlparse(str(value or "").strip())
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def publication_timestamp(value: Any) -> str | None:
    """Return a normalized timestamp or None; URLs and ids are never dates."""
    raw = str(value or "").strip()
    if not raw or raw.startswith(("http://", "https://")):
        return None
    # RFC 822 / Atom dates are accepted by email.utils; ISO dates by datetime.
    try:
        from email.utils import parsedate_to_datetime

        parsed = parsedate_to_datetime(raw)
        if parsed is not None:
            return parsed.isoformat()
    except (TypeError, ValueError, IndexError):
        pass
    normalized = raw.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(normalized).isoformat()
    except ValueError:
        return None


def provenance_for_article(
    article: dict[str, Any],
    *,
    source: str,
    endpoint: str,
    extraction_method: str,
    http_statuses: Iterable[int] | None,
    pagination: dict[str, Any] | None,
) -> dict[str, Any]:
    body = str(article.get("body") or "")
    return {
        "source": source,
        "url": article.get("url"),
        "source_article_id": article.get("source_article_id") or article.get("id") or article.get("guid"),
        "publication_timestamp": publication_timestamp(article.get("published") or article.get("date")),
        "extraction_method": extraction_method,
        "body_length": len(body),
        "body_sha256": sha256(body.encode("utf-8")).hexdigest() if body.strip() else None,
        "http_status": list(http_statuses or []),
        "endpoint": endpoint,
        "pagination": deepcopy(pagination or {}),
    }


def update_publication_bounds(ledger: dict[str, Any], articles: Iterable[dict[str, Any]]) -> None:
    timestamps = [
        publication_timestamp(article.get("published") or article.get("date"))
        for article in articles
    ]
    timestamps = [timestamp for timestamp in timestamps if timestamp]
    if timestamps:
        ledger["first_publication_timestamp"] = min(timestamps)
        ledger["last_publication_timestamp"] = max(timestamps)
    ledger["oldest_article_seen"] = ledger["first_publication_timestamp"]
    ledger["newest_article_seen"] = ledger["last_publication_timestamp"]

