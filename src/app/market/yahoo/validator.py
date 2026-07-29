import json
from src.app.market.interfaces import MarketPayloadValidator
from src.engine.primitives import TransportResult, ValidationResult, ValidationSeverity

class YahooPayloadValidator(MarketPayloadValidator):
    """Zero-trust validation layer determining whether a raw string is usable market data."""

    def validate(self, transport_result: TransportResult) -> ValidationResult:
        payload = transport_result.payload
        provider = transport_result.provider

        if not payload or not isinstance(payload, str):
            return ValidationResult(False, "EMPTY_PAYLOAD", ValidationSeverity.CRITICAL, provider)

        stripped = payload.strip()
        
        # 1. Detect HTML interceptions (CAPTCHA / Scraper Blocks)
        if stripped.startswith("<!DOCTYPE html") or stripped.startswith("<html"):
            if "captcha" in stripped.lower() or "cloudflare" in stripped.lower():
                return ValidationResult(False, "CAPTCHA_INTERCEPTION", ValidationSeverity.CRITICAL, provider)
            return ValidationResult(False, "HTML_BLOCK_PAGE", ValidationSeverity.CRITICAL, provider)

        # 2. Assert valid JSON structure
        try:
            parsed = json.loads(stripped)
        except json.JSONDecodeError:
            return ValidationResult(False, "MALFORMED_JSON", ValidationSeverity.CRITICAL, provider)

        if not isinstance(parsed, dict):
            return ValidationResult(False, "INVALID_ROOT_STRUCTURE", ValidationSeverity.CRITICAL, provider)

        # 3. Detect explicit provider error payloads
        if "finance" in parsed and "error" in parsed["finance"] and parsed["finance"]["error"]:
            err_code = parsed["finance"]["error"].get("code", "UNKNOWN_ERROR")
            return ValidationResult(False, f"PROVIDER_ERROR_{err_code}", ValidationSeverity.WARNING, provider)

        # 4. Assert required nested chart arrays
        chart = parsed.get("chart", {})
        results = chart.get("result")

        if not results or not isinstance(results, list) or len(results) == 0:
            return ValidationResult(False, "EMPTY_CHART_RESULT", ValidationSeverity.WARNING, provider)

        # 5. Assert canonical market metadata anchors
        meta = results[0].get("meta", {})
        required_meta_keys = ["regularMarketPrice", "symbol", "currency", "exchangeName", "regularMarketTime"]
        
        for key in required_meta_keys:
            if key not in meta or meta[key] is None:
                return ValidationResult(False, f"MISSING_REQUIRED_FIELD_{key.upper()}", ValidationSeverity.CRITICAL, provider)

        return ValidationResult(True, "OK", ValidationSeverity.NONE, provider)
