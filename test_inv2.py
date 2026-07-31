import requests
import json
import re
headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
r = requests.get("https://www.investegate.co.uk/", headers=headers)
html = r.text
print(html[:300])
if "api" in html.lower():
    print("Found API mentions.")
