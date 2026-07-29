from pydantic import BaseModel, Field, ConfigDict
from typing import List, Dict, Any, Optional
from datetime import datetime
from enum import Enum

class ExecutionStatus(str, Enum):
    PENDING = "Pending"
    EXECUTING = "Executing"
    PAUSED = "Paused"
    COMPLETED = "Completed"
    FAILED = "Failed"

class ExecutionPolicy(BaseModel):
    policy_id: str = Field(..., description="e.g., POLICY_FAST, POLICY_FULL_DD")
    name: str
    parallel_execution: bool
    retry_policy: str
    stop_on_failure: bool
    allow_async: bool
    cache_strategy: str = Field(..., description="e.g., USE_CACHE, FORCE_REFRESH")
    budget_limit_tokens: int
    timeout_seconds: int
    max_ai_calls: int

class PlaybookTemplate(BaseModel):
    playbook_id: str
    version: str
    canonical_name: str
    supported_ontology_nodes: List[str]
    supported_instruments: List[str]
    jurisdiction: str = "GLOBAL"
    stages: Dict[str, List[str]] = Field(..., description="Ordered dictionary of Stages mapping to Module IDs")

class ExecutionPlan(BaseModel):
    """Immutable representation of the intended investigation."""
    model_config = ConfigDict(frozen=True)
    
    plan_id: str
    event_id: str
    playbook_id: str
    policy_id: str
    
    # Pre-calculated by the Planner
    compiled_stages: Dict[str, List[str]] = Field(..., description="Filtered, applicable modules grouped by stage")
    topological_sequence: List[str] = Field(..., description="The absolute DAG execution order")
    required_capabilities: List[str] = Field(..., description="e.g., ['High Context Extraction', 'Quantitative Reasoning']")
    
    # Estimations
    estimated_ai_calls: int
    estimated_tokens: int
    estimated_runtime_seconds: int
    critical_path_modules: List[str]
    
    created_at: datetime = Field(default_factory=datetime.now)

class ExecutionRun(BaseModel):
    """Mutable runtime state of an ExecutionPlan."""
    run_id: str
    plan_id: str = Field(..., description="Pointer to the immutable ExecutionPlan")
    status: ExecutionStatus = ExecutionStatus.PENDING
    
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    
    # State tracking
    completed_modules: List[str] = Field(default_factory=list)
    failed_modules: List[str] = Field(default_factory=list)
    retries_exhausted: List[str] = Field(default_factory=list)
    
    # Telemetry
    actual_ai_calls: int = 0
    actual_tokens_used: int = 0
    actual_runtime_seconds: int = 0
    
    module_results: Dict[str, Any] = Field(default_factory=dict, description="Outputs of completed modules")
    errors: List[str] = Field(default_factory=list)
