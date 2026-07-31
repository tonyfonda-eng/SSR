import requests
from bs4 import BeautifulSoup

headers = {"User-Agent": "Mozilla/5.0"}
url = "https://www.investegate.co.uk/announcement/rns/aib-group-cdi---aibg/aib-group-plc-transaction-in-own-shares/9699460"
r = requests.get(url, headers=headers)
soup = BeautifulSoup(r.text, 'html.parser')

print(r.text[:500])
main = soup.find('main')
if main:
    print(main.get_text()[:200])
