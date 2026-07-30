import os
import json
from datetime import datetime
from typing import Dict, List, Any, Set, Callable, Optional
from src.knowledge.schemas.epistemology import CalculationResult

class EventStore:
    def __init__(self, event_id: str):
        self.event_id = event_id
        self.ledger: List[Dict[str, Any]] = []

    def record(self, action: str, details: Dict[str, Any] = None):
        entry = {"timestamp": datetime.now().isoformat(), "action": action, "details": details or {}}
        self.ledger.append(entry)
        print(f"[{entry['timestamp']}] {action}")

class EventBus:
    """Reactive Event Bus. Automatically maps published objects to calculations and alert subscribers."""
    def __init__(self, ctx: 'ExecutionContext', registry_manager: Any, implementation_map: Dict[str, Callable]):
        self.ctx = ctx
        self.registry = registry_manager
        self.impl_map = implementation_map
        self.active_calcs: List[str] = []
        self._subscribers: List[Callable[[str, Any], None]] = []

    def configure_active_calculations(self, calc_ids: List[str]):
        self.active_calcs = calc_ids

    def subscribe(self, callback: Callable[[str, Any], None]):
        self._subscribers.append(callback)

    def publish(self, object_id: str, payload: Any):
        """Publishes an object and immediately triggers dependent downstream calculations."""
        self.ctx.available_objects.add(object_id)
        if isinstance(payload, CalculationResult):
            self.ctx.calculation_results[object_id] = payload
        else:
            self.ctx.market_snapshots[object_id] = payload

        for sub in self._subscribers:
            sub(object_id, payload)

        for calc_id in self.active_calcs:
            calc_def = self.registry.get_calculation(calc_id)
            if not calc_def: continue
            
            output_obj = calc_def["produces"]
            if output_obj in self.ctx.available_objects:
                continue
                
            reqs = calc_def["required_inputs"]
            triggers = calc_def.get("trigger_on", [])
            
            if object_id in reqs or object_id in triggers:
                if all(r in self.ctx.available_objects for r in reqs):
                    inputs = {}
                    for r in reqs:
                        if r in self.ctx.market_snapshots: 
                            inputs[r] = self.ctx.market_snapshots[r]
                        elif r in self.ctx.calculation_results: 
                            inputs[r] = self.ctx.calculation_results[r]
                    
                    # Explicitly inject optional secondary considerations (like CVRs) into calculation inputs
                    if "OBJ.FIN.CVR_CONSIDERATION" in self.ctx.market_snapshots:
                        inputs["OBJ.FIN.CVR_CONSIDERATION"] = self.ctx.market_snapshots["OBJ.FIN.CVR_CONSIDERATION"]
                    
                    func_name = calc_def["implementation"]["function"]
                    func = self.impl_map[func_name]
                    
                    res_obj = func(inputs)
                    self.ctx.store.record(f"REACTIVE_TRIGGER: {calc_id} fired by {object_id}")
                    
                    self.publish(output_obj, res_obj)

class ExecutionContext:
    def __init__(self, event_id: str, registry_manager: Any = None, implementation_map: Dict[str, Callable] = None):
        self.event_id = event_id
        self.store = EventStore(event_id)
        self.bus = EventBus(self, registry_manager, implementation_map or {})
        
        self.completed_modules: Set[str] = set()
        self.available_objects: Set[str] = set()
        self.market_snapshots: Dict[str, Any] = {}
        self.calculation_results: Dict[str, CalculationResult] = {}
        
        self.store.record("CONTEXT_INITIALIZED")

    def snapshot(self, filepath: str):
        state = {
            "event_id": self.event_id,
            "completed_modules": list(self.completed_modules),
            "available_objects": list(self.available_objects),
            "market_snapshots": self.market_snapshots,
            "calculation_results": {k: v.model_dump() for k, v in self.calculation_results.items()},
            "ledger": self.store.ledger
        }
        with open(filepath, 'w') as f:
            json.dump(state, f, default=str, indent=2)
        self.store.record(f"SNAPSHOT_SAVED: {filepath}")

    @classmethod
    def load(cls, filepath: str, registry_manager: Any, implementation_map: Dict[str, Callable]) -> 'ExecutionContext':
        with open(filepath, 'r') as f:
            state = json.load(f)
            
        ctx = cls(state["event_id"], registry_manager, implementation_map)
        ctx.completed_modules = set(state["completed_modules"])
        ctx.available_objects = set(state["available_objects"])
        ctx.market_snapshots = state["market_snapshots"]
        
        for k, v in state["calculation_results"].items():
            ctx.calculation_results[k] = CalculationResult(**v)
            
        ctx.store.ledger = state["ledger"]
        ctx.store.record(f"SNAPSHOT_LOADED: {filepath}")
        return ctx

class TaskPlanner:
    def __init__(self, root_dir: str):
        self.root_dir = root_dir
        self.specs = {}
        self.load_specifications()

    def load_specifications(self):
        spec_dir = os.path.join(self.root_dir, 'src/playbooks/specifications/universal')
        if os.path.exists(spec_dir):
            for file in os.listdir(spec_dir):
                if file.endswith(".json"):
                    with open(os.path.join(spec_dir, file), 'r') as f:
                        data = json.load(f)
                        self.specs[data["module_id"]] = data
