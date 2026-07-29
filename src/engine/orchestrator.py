from typing import List
from src.engine.core import RegistryManager, SchemaValidator, GraphLinker
from src.engine.runtime import ExecutionContext
from src.engine.calculations import CALC_IMPLEMENTATION_MAP

class ExecutionOrchestrator:
    def __init__(self, root_dir: str):
        self.root_dir = root_dir
        self.registry = RegistryManager(root_dir)
        self.validator = SchemaValidator(self.registry)

    def bootstrap_context(self, event_id: str, active_calcs: List[str]) -> ExecutionContext:
        """Creates a context pre-configured with active calculations mapped to the reactive bus."""
        ctx = ExecutionContext(event_id, self.registry, CALC_IMPLEMENTATION_MAP)
        ctx.bus.configure_active_calculations(active_calcs)
        return ctx
