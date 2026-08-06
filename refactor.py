import os
import re

files_to_process = [
    "src/scrapers/businesswire.py",
    "src/scrapers/edgar.py",
    "src/scrapers/edgar_items.py",
    "src/scrapers/googlenews.py",
    "src/scrapers/nasdaq.py",
    "src/scrapers/lse.py",
    "src/scrapers/tsx.py",
    "src/scrapers/sedar.py",
    "src/scrapers/hkex.py",
    "src/scrapers/globenewswire.py",
    "src/scrapers/asx.py",
    "src/scrapers/prnewswire.py",
    "src/build_docs.py"
]

patch_pattern = re.compile(
    r'(?m)^# --- WAF BYPASS WRAPPER ---$.*?^# --------------------------$',
    re.MULTILINE | re.DOTALL
)

for fpath in files_to_process:
    with open(fpath, "r", encoding="utf-8") as f:
        content = f.read()

    # If it contains the patch
    if patch_pattern.search(content):
        # Add import for get_session
        content = patch_pattern.sub("from src.scrapers.client import get_session", content)
        
        # Replace requests.get( with get_session().get(
        content = re.sub(r'\brequests\.get\(', 'get_session().get(', content)
        
        with open(fpath, "w", encoding="utf-8") as f:
            f.write(content)
        print(f"Refactored {fpath}")
    else:
        print(f"No patch found in {fpath}")
