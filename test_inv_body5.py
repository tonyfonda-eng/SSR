import requests
from bs4 import BeautifulSoup

headers = {"User-Agent": "Mozilla/5.0"}
url = "https://www.investegate.co.uk/announcement/rns/aib-group-cdi---aibg/aib-group-plc-transaction-in-own-shares/9699460"
r = requests.get(url, headers=headers)
soup = BeautifulSoup(r.text, 'html.parser')
divs = soup.find_all('div')
for d in divs:
    text = d.get_text(separator="\n", strip=True)
    if len(text) > 1000 and "Transaction in Own Shares" in text:
        print(d.get('class'), d.get('id'))
        break
