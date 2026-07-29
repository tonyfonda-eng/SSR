from pydantic import BaseModel, Field
from typing import List, Dict, Optional, Any
from enum import Enum

class MaturityLevel(str, Enum):
    DRAFT = "Draft"
    VALIDATED = "Validated"
    VERIFIED = "Verified"
    INSTITUTIONAL = "Institutional"
    DEPRECATED = "Deprecated"

class CachePolicy(str, Enum):
    IMMUTABLE = "immutable"
    SNAPSHOT_BOUND = "snapshot_bound"
    VOLATILE = "volatile"

class CalcImplementation(BaseModel):
    type: str
    function_name: str

class CalculationTestCase(BaseModel):
    test_id: str
    input_values: Dict[str, Any]
    expected_output: float
    absolute_tolerance: float = 0.0001

class CalculationDefinition(BaseModel):
    calc_id: str
    version: str = "1.0"
    name: str
    family: str
    description: str
    required_inputs: List[str]
    output_object: str
    trigger_on: List[str] = Field(default_factory=list, description="Objects or calcs that trigger re-evaluation")
    implementation: CalcImplementation
    cache_policy: CachePolicy = CachePolicy.IMMUTABLE
    assumptions: List[str] = Field(default_factory=list)
    test_vectors: List[CalculationTestCase]
    maturity: MaturityLevel = MaturityLevel.DRAFT

class ExpectedOutputContract(BaseModel):
    local_key: str
    schema_id: str
    object_id: str

class ActivationCondition(BaseModel):
    """Future-proof specification activation rules."""
    requires_modules: List[str] = Field(default_factory=list)
    required_objects: List[str] = Field(default_factory=list)
    condition_expression: Optional[str] = Field(None)
    priority: int = 100
    optional: bool = False

class ResearchSpecification(BaseModel):
    """Declarative Extractor Specification with Dynamic Activation Rules."""
    spec_id: str
    module_id: str
    version: str = "3.2"
    objective: str
    
    activation: ActivationCondition = Field(default_factory=ActivationCondition)
    
    required_artifact_types: List[str]
    minimum_evidence_tier: str
    
    research_questions: List[str]
    decision_rules: List[str]
    ambiguity_strategy: str
    confidence_method: str
    
    produces_outputs: List[ExpectedOutputContract]
    
    validation_rules: List[str]
    failure_conditions: List[str]
    maturity: MaturityLevel = MaturityLevel.DRAFT
