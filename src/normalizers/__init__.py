from .germany import normalize as normalize_germany
from .italy import normalize as normalize_italy
from .france import normalize as normalize_france
from .spain import normalize as normalize_spain
from .nordics import normalize as normalize_nordics

def get_normalizer(country):
    if not country: return None
    c = country.lower()
    if c == "germany": return normalize_germany
    if c == "italy": return normalize_italy
    if c == "france": return normalize_france
    if c == "spain": return normalize_spain
    if c in ["sweden", "norway", "netherlands", "finland", "denmark"]: return normalize_nordics
    if c == "switzerland": return normalize_germany # German/French
    return None
