import json
from datetime import datetime
from typing import Dict, Any, List
from src.engine.connectors import MarketDataConnector, MarketDataAdapter
from src.knowledge.schemas.epistemology import CandidateAssertion, ConfidenceMethod

class YahooFinanceConnector(MarketDataConnector):
    def fetch_market_price(self, ticker: str) -> Dict[str, Any]:
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}"
        return json.loads(self.transport.get(url))

    def fetch_option_chain(self, ticker: str) -> Dict[str, Any]:
        url = f"https://query1.finance.yahoo.com/v7/finance/options/{ticker}"
        return json.loads(self.transport.get(url))

class YahooFinanceAdapter(MarketDataAdapter):
    def adapt_price_snapshot(self, raw_payload: Dict[str, Any], event_id: str) -> CandidateAssertion:
        try:
            res = raw_payload["chart"]["result"][0]["meta"]
            return CandidateAssertion(
                candidate_id=f"CND.MKT.{res['symbol']}.PRICE",
                event_id=event_id,
                schema_id="SCHEMA.MKT.SNAPSHOT",
                object_id="OBJ.MKT.PRICE_SNAPSHOT",
                value_payload={
                    "timestamp": datetime.fromtimestamp(res["regularMarketTime"]).isoformat(),
                    "price": float(res["regularMarketPrice"]),
                    "currency": res["currency"]
                },
                basis_observations=[],
                confidence_method=ConfidenceMethod.EXACT_MATCH,
                extractor_profile_id="CONN.YF.PRICE.v1"
            )
        except (KeyError, TypeError) as e:
            raise ValueError(f"Failed to parse live Yahoo data structures: {e}")

    def adapt_chain(self, raw_payload: Dict[str, Any], event_id: str) -> List[CandidateAssertion]:
        candidates = []
        try:
            option_data = raw_payload["optionChain"]["result"][0]
            underlying = option_data["underlyingSymbol"]
            
            for option_set in option_data.get("options", []):
                for call in option_set.get("calls", []):
                    candidates.append(self._build_contract(call, underlying, "Call", event_id))
                for put in option_set.get("puts", []):
                    candidates.append(self._build_contract(put, underlying, "Put", event_id))
        except (KeyError, IndexError):
            pass
        return candidates

    def _build_contract(self, contract: dict, underlying: str, opt_type: str, event_id: str) -> CandidateAssertion:
        exp_ts = contract.get("expiration", 0)
        exp_iso = datetime.fromtimestamp(exp_ts).isoformat() if exp_ts else datetime.now().isoformat()
        
        return CandidateAssertion(
            candidate_id=f"CND.OPT.{contract.get('contractSymbol', 'UNKNOWN')}",
            event_id=event_id,
            schema_id="SCHEMA.OPT.CONTRACT",
            object_id="OBJ.OPT.OPTION_CONTRACT",
            value_payload={
                "underlying_ticker": underlying,
                "occ_symbol": contract.get("contractSymbol", ""),
                "strike": float(contract.get("strike", 0.0)),
                "expiration": exp_iso,
                "option_type": opt_type,
                "exercise_style": "American",
                "multiplier": 100.0,
                "deliverable": "100 shares",
                "settlement_type": "Physical",
                "listing_exchange": "OPRA",
                "is_adjusted": False,
                "contract_size": 100,
                "currency": "USD",
                "premium_price": float(contract.get("lastPrice", 0.0))
            },
            basis_observations=[],
            confidence_method=ConfidenceMethod.EXACT_MATCH,
            extractor_profile_id="CONN.YF.CHAIN.v1"
        )
