import sys
import os
from datetime import datetime

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from src.knowledge.schemas.core import Announcement, CorporateAction, Instrument, Event, Assessment, Decision
from src.utils.id_generator import generate_id
from src.ontology.engine import Ontology

def main():
    print("==========================================================")
    print(" 6-TIER KNOWLEDGE GRAPH: IMMUTABLE AUDIT TRAIL LOGGED     ")
    print("==========================================================\n")
    
    # Tier 1: Announcement
    announcement_id = generate_id("ANNC", "dgsr-boardroom-2026")
    print(f"[Tier 1: Announcement] ID: {announcement_id} | Discovered: {datetime.now().strftime('%Y-%m-%d %H:%M')}")

    # Tier 2: Corporate Action
    action_id = generate_id("ACTION", f"DGSR-{datetime.now().strftime('%Y%m%d')}")
    print(f"[Tier 2: Corp Action]  ID: {action_id} | Entity: DGSR Corporation")

    # Tier 3: Instrument
    instrument_id = generate_id("CASE", f"{action_id}-OPTIONS")
    print(f"[Tier 3: Instrument]   ID: {instrument_id} | Type: Options Contracts")

    # Tier 4: Event (Immutable)
    event_id = generate_id("EVENT", f"{instrument_id}-CC-001")
    print(f"[Tier 4: Event]        ID: {event_id} | Ontology: CC-001 (Cash Merger)")

    # Tier 5: Assessment (Mutable/Time-Series)
    assessment_id = generate_id("CASE", f"{event_id}-PASS1")
    print(f"[Tier 5: Assessment]   ID: {assessment_id} | Confidence: 0.91 | AI: Grok-2")

    # Tier 6: Decision (Execution Log)
    decision_id = generate_id("CASE", f"{assessment_id}-EXEC")
    decision = Decision(
        decision_id=decision_id,
        assessment_id=assessment_id,
        action_taken="Execute Trade",
        rationale="High probability cash merger; option chain implies heavy premium decay.",
        execution_notes="Sell DGSR naked calls via Interactive Brokers to capture IV crush."
    )
    print(f"[Tier 6: Decision]     ID: {decision.decision_id} | Action: {decision.action_taken}")
    print(f"  └─ Rationale: {decision.rationale}")
    print(f"  └─ Notes: {decision.execution_notes}")
    print("\n==========================================================")

if __name__ == "__main__":
    main()
