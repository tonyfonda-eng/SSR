import json
import os
import uuid
from datetime import datetime
from typing import Dict, List

def resolve_dag(modules_dict: Dict[str, dict]) -> List[str]:
    """Kahn's Algorithm for Topological Sorting to resolve module execution order."""
    in_degree = {m: 0 for m in modules_dict}
    adj = {m: [] for m in modules_dict}
    
    for m_id, m_data in modules_dict.items():
        for dep in m_data.get("dependencies", []):
            if dep in modules_dict:  # Only track dependencies included in this specific plan
                adj[dep].append(m_id)
                in_degree[m_id] += 1
                
    queue = [m for m in in_degree if in_degree[m] == 0]
    sorted_modules = []
    
    while queue:
        node = queue.pop(0)
        sorted_modules.append(node)
        for neighbor in adj[node]:
            in_degree[neighbor] -= 1
            if in_degree[neighbor] == 0:
                queue.append(neighbor)
                
    if len(sorted_modules) != len(modules_dict):
        raise ValueError("Cycle detected in module dependencies! Topological sort failed.")
        
    return sorted_modules

class ExecutionPlanner:
    def __init__(self, root_dir: str):
        self.playbooks = self._load_json_dir(os.path.join(root_dir, 'src/playbooks/templates'))
        self.modules = self._load_json_dir(os.path.join(root_dir, 'src/playbooks/modules'))
        self.policies = self._load_json_dir(os.path.join(root_dir, 'src/playbooks/policies'))
        
    def _load_json_dir(self, directory: str) -> Dict[str, dict]:
        data = {}
        if not os.path.exists(directory):
            return data
        for root, _, files in os.walk(directory):
            for file in files:
                if file.endswith('.json') and file != 'taxonomy.json':
                    try:
                        with open(os.path.join(root, file), 'r') as f:
                            content = json.load(f)
                            items = content if isinstance(content, list) else [content]
                            for item in items:
                                if "playbook_id" in item: data[item["playbook_id"]] = item
                                elif "module_id" in item: data[item["module_id"]] = item
                                elif "policy_id" in item: data[item["policy_id"]] = item
                    except Exception as e:
                        print(f"Error loading {file}: {e}")
        return data
        
    def compile_plan(self, event_id: str, playbook_id: str, policy_id: str) -> dict:
        playbook = self.playbooks.get(playbook_id)
        policy = self.policies.get(policy_id)
        
        if not playbook: raise ValueError(f"Playbook '{playbook_id}' not found.")
        if not policy: raise ValueError(f"Policy '{policy_id}' not found.")
        
        # 1. Flatten modules from playbook stages
        applicable_modules = {}
        for stage, mods in playbook.get("stages", {}).items():
            for m_id in mods:
                # If module isn't physically created yet, stub it to prove the DAG works
                mod = self.modules.get(m_id, {"module_id": m_id, "dependencies": [], "estimated_cost_tokens": 1000})
                applicable_modules[m_id] = mod
                    
        # 2. Resolve Dependencies & Topological Sort
        execution_sequence = resolve_dag(applicable_modules)
            
        # 3. Estimations against Policy Budget
        est_tokens = sum(m.get("estimated_cost_tokens", 1000) for m in applicable_modules.values())
        budget_cap = policy.get("budget_limit_tokens", 50000)
        
        plan = {
            "plan_id": f"PLAN_{uuid.uuid4().hex[:8].upper()}",
            "event_id": event_id,
            "playbook_id": playbook_id,
            "policy_id": policy_id,
            "status": "PENDING (FROZEN)",
            "topological_sequence": execution_sequence,
            "estimations": {
                "estimated_tokens": est_tokens,
                "policy_budget": budget_cap,
                "budget_compliant": est_tokens <= budget_cap
            },
            "created_at": datetime.now().isoformat()
        }
        return plan
