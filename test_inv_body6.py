import requests
from bs4 import BeautifulSoup
import re

headers = {"User-Agent": "Mozilla/5.0"}
url = "https://www.investegate.co.uk/announcement/rns/aib-group-cdi---aibg/aib-group-plc-transaction-in-own-shares/9699460"
r = requests.get(url, headers=headers)
soup = BeautifulSoup(r.text, 'html.parser')
# Find the div that contains the preformatted text or specific RNS classes
article = soup.find('div', id='article-content')
if not article:
    # Investegate puts the text inside an iframe or directly in the page
    iframe = soup.find('iframe')
    if iframe:
        print("Found iframe:", iframe.get('src'))
    else:
        # Just grab the biggest div that has no children divs
        content = soup.find('div', class_=re.compile("news-content|announcementContent|article-body|page-content"))
        print(content.get_text()[:300] if content else "No content container found")
        
        # Check text length directly
        print("Total text length:", len(soup.get_text()))
