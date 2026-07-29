import sys
import os

# Align the root path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

print("==================================================")
print("       SSR ARCHITECTURE & SCHEMAS CHECK           ")
print("==================================================\n")

# 1. Structural Directory Audit
expected_paths = [
    "docs/ROADMAP.md",
    "docs/ONTOLOGY.md",
    "docs/PLAYBOOKS.md",
    "docs/CODING_STANDARDS.md",
    "src/utils/id_generator.py",
    "src/knowledge/schemas/core.py",
    "src/parsers/document_parser.py",
    "src/parsers/ai_extractor.py",
    "src/providers/base_provider.py",
    "src/providers/router.py",
    "src/utils/sheets_client.py"
]

print("1. VERIFYING SYSTEM FILE LAYOUT:")
missing_files = 0
for path in expected_paths:
    if os.path.exists(path):
        print(f"  [✓] Found: {path}")
    else:
        print(f"  [X] MISSING: {path}")
        missing_files += 1

# 2. Functional Schema & Logic Verification
print("\n2. TESTING LOGIC & MATRIX MATH ENGINE:")
try:
    from src.knowledge.schemas.core import Event, SourceReliability
    from src.utils.id_generator import generate_id
    
    # Test deterministic ID mapping
    id_1 = generate_id("EVENT", "tender-offer-2026")
    id_2 = generate_id("EVENT", "tender-offer-2026")
    assert id_1 == id_2, "Deterministic ID failure"
    print("  [✓] Deterministic Hash Generator: Stable")

    # Test tri-factor confidence formula
    event = Event(
        event_id="EVENT-CHECK",
        case_id="CASE-CHECK",
        source_reliability=SourceReliability.A, # Weight: 0.95
        extraction_confidence=0.90,
        research_confidence=0.80
    )
    # 0.90 * 0.80 * 0.95 = 0.684
    assert event.calculate_overall_confidence() == 0.684, "Confidence calculation matrix mismatch"
    print("  [✓] Tri-Factor Confidence Equation: Verified Math (0.684)")

except Exception as e:
    print(f"  [X] Functional check failed: {e}")
    missing_files += 1

print("\n==================================================")
if missing_files == 0:
    print(" STATUS: SYSTEM HEALTHY & COMPLIANT WITH MANUAL ")
else:
    print(f" STATUS: DEGRADED ({missing_files} items need attention) ")
print("==================================================")
