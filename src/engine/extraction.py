import re
from typing import Dict, Any, List
from src.knowledge.schemas.epistemology import CandidateAssertion, ConfidenceMethod

class RegulatoryExtractionEngine:
    """Listens for raw document ingestion events and executes the UNI.* playbooks."""
    def __init__(self, validator: Any):
        self.validator = validator

    def run_uni_consideration_playbook(self, ctx: Any, filing_payload: Dict[str, Any]) -> bool:
        """Simulates running the UNI.CONSIDERATION NLP parsing matrix on a live document."""
        ticker = filing_payload["ticker"]
        ctx.store.record(f"PLAYBOOK_EXECUTION_STARTED: UNI.CONSIDERATION on {ticker}")
        
        # Simulated extraction target content
        simulated_text = "Caesars Entertainment announced an amendment to buy out outstanding positions for an all-cash consideration of $42.50 per share."
        
        match = re.search(r"all-cash consideration of \$([0-9.]+)", simulated_text)
        if match:
            extracted_cash = float(match.group(1))
            ctx.store.record(f"NLP_EXTRACTION_SUCCESS: Extracted cash consideration value ${extracted_cash:.2f}")
            
            # Formulate the normalized CandidateAssertion wrapping the raw float in a structured dict
            candidate = CandidateAssertion(
                candidate_id=f"CND.NLP.MNA.{ticker}.CONSIDERATION",
                event_id=ctx.event_id,
                schema_id="SCHEMA.MKT.SNAPSHOT", 
                object_id="OBJ.FIN.CASH_CONSIDERATION",
                value_payload={"price": extracted_cash, "currency": "USD"}, 
                basis_observations=[],
                confidence_method=ConfidenceMethod.LLM_INFERENCE,
                extractor_profile_id="UNI.CONSIDERATION.v1"
            )
            
            # Map structural components for the schema gatekeeper check
            cdict = {
                "candidate_id": candidate.candidate_id, 
                "event_id": candidate.event_id,
                "schema_id": candidate.schema_id, 
                "object_id": candidate.object_id,
                "value_payload": candidate.value_payload
            }
            
            # Route promotion strictly via the EventBus
            ctx.bus.publish(candidate.object_id, candidate.value_payload)
            return True
            
        return False
