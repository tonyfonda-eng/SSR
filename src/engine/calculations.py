import time
import hashlib
import json
from src.knowledge.schemas.epistemology import CalculationResult

class PricingEngine:
    @staticmethod
    def calculate_intrinsic(option_type: str, strike: float, underlying_price: float) -> float:
        if option_type.lower() == "call":
            return max(0.0, underlying_price - strike)
        return max(0.0, strike - underlying_price)
        
    @staticmethod
    def calculate_extrinsic(premium: float, intrinsic: float) -> float:
        return max(0.0, premium - intrinsic)

def generate_provenance(version: str):
    def decorator(func):
        def wrapper(inputs, *args, **kwargs):
            t0 = time.perf_counter()
            raw_result = func(inputs, *args, **kwargs)
            t1 = time.perf_counter()
            
            safe_inputs = {}
            for k, v in inputs.items():
                if isinstance(v, CalculationResult):
                    safe_inputs[k] = str(v.result_value)
                else:
                    safe_inputs[k] = str(v)
                    
            input_hash = hashlib.sha256(json.dumps(safe_inputs, sort_keys=True).encode()).hexdigest()
            
            return CalculationResult(
                result_value=raw_result,
                input_object_ids=list(inputs.keys()),
                input_hash=input_hash,
                implementation_version=version,
                execution_time_ms=(t1 - t0) * 1000
            )
        return wrapper
    return decorator

@generate_provenance(version="1.0.0")
def calc_obj_opt_intrinsic_value(inputs: dict) -> float:
    contract = inputs.get("OBJ.OPT.OPTION_CONTRACT")
    snapshot = inputs.get("OBJ.MKT.PRICE_SNAPSHOT")
    if not contract or not snapshot: raise ValueError("Missing inputs for ITM Intrinsic calculation")
    return PricingEngine.calculate_intrinsic(contract["option_type"], contract["strike"], snapshot["price"])

@generate_provenance(version="1.0.0")
def calc_obj_opt_extrinsic_value(inputs: dict) -> float:
    premium_snapshot = inputs.get("OBJ.MKT.PREMIUM_SNAPSHOT")
    intrinsic_obj = inputs.get("OBJ.OPT.INTRINSIC_VALUE")
    if not premium_snapshot or not intrinsic_obj: raise ValueError("Missing inputs for Extrinsic calculation")
    return PricingEngine.calculate_extrinsic(premium_snapshot["price"], intrinsic_obj.result_value)

@generate_provenance(version="1.0.0")
def calc_analytics_opt_arb_break_even(inputs: dict) -> float:
    contract = inputs.get("OBJ.OPT.OPTION_CONTRACT")
    premium_snapshot = inputs.get("OBJ.MKT.PREMIUM_SNAPSHOT")
    if not contract or not premium_snapshot: raise ValueError("Missing inputs for Break-Even calculation")
    if contract["option_type"].lower() == "call":
        return contract["strike"] + premium_snapshot["price"]
    return contract["strike"] - premium_snapshot["price"]

@generate_provenance(version="1.0.0")
def calc_analytics_opt_assignment_risk(inputs: dict) -> float:
    contract = inputs.get("OBJ.OPT.OPTION_CONTRACT")
    intrinsic = inputs.get("OBJ.OPT.INTRINSIC_VALUE")
    extrinsic = inputs.get("OBJ.OPT.EXTRINSIC_VALUE")
    if not contract or intrinsic is None or extrinsic is None: 
        raise ValueError("Missing state layers for Assignment heuristic execution")
    if contract["option_type"].lower() == "call":
        if intrinsic.result_value > 0.0:
            if extrinsic.result_value < 0.10: return 0.95
            return 0.45
        return 0.01
    return 0.0

@generate_provenance(version="1.0.0")
def calc_port_position_pnl(inputs: dict) -> float:
    position = inputs.get("OBJ.PORT.POSITION_RECORD")
    premium = inputs.get("OBJ.MKT.PREMIUM_SNAPSHOT")
    if not position or not premium: raise ValueError("Missing state layers for Position PnL execution")
    return (premium["price"] - position["average_entry_price"]) * position["quantity"] * position.get("multiplier", 100.0)

@generate_provenance(version="1.0.0")
def calc_mna_opt_merger_payoff(inputs: dict) -> float:
    contract = inputs.get("OBJ.OPT.OPTION_CONTRACT")
    position = inputs.get("OBJ.PORT.POSITION_RECORD")
    buyout_cash = inputs.get("OBJ.FIN.CASH_CONSIDERATION")
    
    if not contract or not position or not buyout_cash:
        raise ValueError("Missing state layers for Merger Payoff execution")
        
    strike = contract["strike"]
    avg_premium = position["average_entry_price"]
    qty = position["quantity"]
    multiplier = position.get("multiplier", 100.0)
    
    # Base cash consideration value
    total_cash_value = buyout_cash["price"]
    
    # Dynamically aggregate secondary considerations (like CVRs) if present in context inputs
    if "OBJ.FIN.CVR_CONSIDERATION" in inputs:
        total_cash_value += inputs["OBJ.FIN.CVR_CONSIDERATION"]["price"]
        
    if contract["option_type"].lower() == "call":
        settlement_value = max(0.0, total_cash_value - strike)
    else:
        settlement_value = max(0.0, strike - total_cash_value)
        
    if position["position_type"] == "short":
        return (avg_premium - settlement_value) * abs(qty) * multiplier
    return (settlement_value - avg_premium) * abs(qty) * multiplier

CALC_IMPLEMENTATION_MAP = {
    "calc_obj_opt_intrinsic_value": calc_obj_opt_intrinsic_value,
    "calc_obj_opt_extrinsic_value": calc_obj_opt_extrinsic_value,
    "calc_analytics_opt_arb_break_even": calc_analytics_opt_arb_break_even,
    "calc_analytics_opt_assignment_risk": calc_analytics_opt_assignment_risk,
    "calc_port_position_pnl": calc_port_position_pnl,
    "calc_mna_opt_merger_payoff": calc_mna_opt_merger_payoff
}
