import requests
from bs4 import BeautifulSoup
import re

headers = {"User-Agent": "Mozilla/5.0"}
url = "https://www.investegate.co.uk/announcement/rns/aib-group-cdi---aibg/aib-group-plc-transaction-in-own-shares/9699460"
r = requests.get(url, headers=headers)
soup = BeautifulSoup(r.text, 'html.parser')
content = soup.find('div', id='announcement-body')
if not content:
    content = soup.find('div', class_=re.compile('announcement-content|article-body'))
print("Body length:", len(content.get_text(strip=True)) if content else "Not found")
