import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from src.financials import get_t12_metrics
import json

metrics = get_t12_metrics("VLTO")
print(json.dumps(metrics, indent=2))
