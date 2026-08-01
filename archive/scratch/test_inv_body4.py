import requests
from bs4 import BeautifulSoup

headers = {"User-Agent": "Mozilla/5.0"}
url = "https://www.investegate.co.uk/announcement/rns/aib-group-cdi---aibg/aib-group-plc-transaction-in-own-shares/9699460"
r = requests.get(url, headers=headers)
soup = BeautifulSoup(r.text, 'html.parser')
body_div = soup.find('div', id='ad-rns-content')
if body_div:
    print(body_div.get_text(separator="\n", strip=True)[:300])
else:
    print("Not found")
