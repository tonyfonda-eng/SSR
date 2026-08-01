import requests
from bs4 import BeautifulSoup

headers = {"User-Agent": "Mozilla/5.0"}
url = "https://www.investegate.co.uk/announcement/rns/aib-group-cdi---aibg/aib-group-plc-transaction-in-own-shares/9699460"
r = requests.get(url, headers=headers)
soup = BeautifulSoup(r.text, 'html.parser')
body_div = soup.find('div', id='announcementContent')
if not body_div:
    body_div = soup.find('div', class_='announcement-details')
if body_div:
    print(body_div.get_text()[:200].strip())
else:
    print("Could not find body div. Available ids:")
    print([d.get('id') for d in soup.find_all('div') if d.get('id')])
