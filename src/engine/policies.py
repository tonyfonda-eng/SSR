from src.engine.transport import TransportPolicy, ExpectedMediaType

class NetworkPolicyRegistry:
    """Declarative, per-host network boundary policies."""
    
    # SEC EDGAR: Conservative, strict XML handling, explicit User-Agent requirements handled by transport
    SEC_EDGAR = TransportPolicy(
        name="SEC_EDGAR_RSS",
        max_retries=4,
        base_backoff=2.0,      # Higher backoff to respect federal infrastructure
        timeout=12.0,
        retryable_codes={429, 500, 502, 503, 504},
        expected_media=ExpectedMediaType.XML
    )

    # Yahoo Finance: Fast, volatile price ticks, strict JSON format verification
    YAHOO_FINANCE = TransportPolicy(
        name="YAHOO_FINANCE_TICK",
        max_retries=2,         # Low retries for real-time market snapshots
        base_backoff=0.5,
        timeout=4.0,           # Fast timeout to drop stale network paths quickly
        retryable_codes={429, 500, 502, 503, 504},
        expected_media=ExpectedMediaType.JSON
    )

    # OCC Options Clearing Corp: Heavy structural adjustments documents
    OCC_MEMOS = TransportPolicy(
        name="OCC_REGULATORY_MEMO",
        max_retries=3,
        base_backoff=1.5,
        timeout=15.0,          # Longer timeout window to handle large document payloads
        retryable_codes={500, 502, 503, 504}, # Don't retry structural client drops
        expected_media=ExpectedMediaType.ANY   # Can return HTML directories or raw PDFs
    )
