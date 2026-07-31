from .germany import normalize as normalize_germany, __version__ as ver_germany
from .italy import normalize as normalize_italy, __version__ as ver_italy
from .france import normalize as normalize_france, __version__ as ver_france
from .spain import normalize as normalize_spain, __version__ as ver_spain
from .nordics import normalize as normalize_nordics, __version__ as ver_nordics

def get_ontology(country):
    """
    Returns a tuple of (normalize_function, version_string) based on country.
    """
    if not country: return None, None
    c = country.lower()
    if c == "germany": return normalize_germany, ver_germany
    if c == "italy": return normalize_italy, ver_italy
    if c == "france": return normalize_france, ver_france
    if c == "spain": return normalize_spain, ver_spain
    if c in ["sweden", "norway", "netherlands", "finland", "denmark"]: return normalize_nordics, ver_nordics
    if c == "switzerland": return normalize_germany, ver_germany # German/French
    return None, None
