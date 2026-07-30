import json
from abc import ABC, abstractmethod
from typing import Any, Dict
from src.engine.transport import PayloadError

class PayloadValidator(ABC):
    """Guarantees vendor payloads match expected structural shapes before adaptation."""
    @abstractmethod
    def validate(self, raw_payload: str) -> Any:
        pass

class YahooPriceValidator(PayloadValidator):
    def validate(self, raw_payload: str) -> Dict[str, Any]:
        try:
            data = json.loads(raw_payload)
        except json.JSONDecodeError:
            raise PayloadError("Payload is not valid JSON")

        if "chart" not in data:
            raise PayloadError("Missing root key: 'chart'")
            
        chart = data["chart"]
        if "result" not in chart or not chart["result"]:
            raise PayloadError("Missing or empty array: 'chart.result'")
            
        result = chart["result"][0]
        if "meta" not in result:
            raise PayloadError("Missing object: 'meta' inside 'result'")
            
        if "regularMarketPrice" not in result["meta"]:
            raise PayloadError("Missing critical float: 'regularMarketPrice' inside 'meta'")

        return data
