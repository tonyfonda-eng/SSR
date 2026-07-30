from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
from enum import Enum
from datetime import datetime

class MaturityLevel(str, Enum):
    EXPERIMENTAL = "Experimental"
    PRODUCTION = "Production"
    INSTITUTIONAL = "Institutional"
    DEPRECATED = "Deprecated"

class SemanticType(str, Enum):
    FACT = "Fact"                 # e.g., "The cash consideration is $50.00"
    INFERENCE = "Inference"       # e.g., "The deal is likely to face antitrust scrutiny"
    OBSERVATION = "Observation"   # e.g., "The options spread is currently 7%"
    ASSESSMENT = "Assessment"     # e.g., "The probability of completion is High"

class EvidenceTier(str, Enum):
    TIER_1_PRIMARY = "Primary Filing (SEC, Court, Regulator)"
    TIER_2_COMPANY = "Company Publication (Press Release, IR Deck)"
    TIER_3_SECONDARY = "Secondary Reporting (Newswire, Terminal)"
    TIER_4_INFERENCE = "AI / Quantitative Inference"

class ResearchSpecification(BaseModel):
    spec_id: str = Field(..., description="e.g., SPEC_U01_MNA_DEF14A")
    module_id: str = Field(..., description="Pointer to the parent module, e.g., U01_DOCUMENT_ANALYSIS")
    version: str = "1.0"
    objective: str
    
    evidence_hierarchy: List[EvidenceTier]
    required_inputs: List[str]
    
    # Typed Outputs with Semantic Classification
    expected_outputs: Dict[str, SemanticType] = Field(..., description="Maps Canonical Output Object to its Semantic Type")
    
    confidence_rules: List[str] = Field(default_factory=list)

class ResearchModule(BaseModel):
    module_id: str = Field(..., description="e.g., U01_DOCUMENT_ANALYSIS")
    version: str = "1.0"
    maturity_level: MaturityLevel = MaturityLevel.EXPERIMENTAL
    layer: str = Field(..., description="Universal, Financial, or Alpha")
    purpose: str
    
    # I/O & Orchestration
    inputs: List[str]
    outputs: List[str] = Field(..., description="List of Canonical Typed Objects")
    dependencies: List[str] = Field(default_factory=list)
    
    # Metadata
    ai_capability: str
    parallelisable: bool = False
    cacheable: bool = True
