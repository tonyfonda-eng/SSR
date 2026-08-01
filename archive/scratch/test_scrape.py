import requests
from bs4 import BeautifulSoup

# 1. EQS News
url = "https://www.eqs-news.com/news-list/"
r = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'})
soup = BeautifulSoup(r.text, 'html.parser')
articles = soup.find_all('a', class_='news-list-item') # guess
if not articles:
    # try another guess
    articles = soup.select('div.news-list a')
print(f"EQS News status: {r.status_code}")
print("EQS News snippet:")
print(r.text[:1000])

# 2. Borsa Italiana
url2 = "https://www.borsaitaliana.it/borsa/notizie/price-sensitive/home.html"
r2 = requests.get(url2, headers={'User-Agent': 'Mozilla/5.0'})
print(f"\nBorsa Italiana status: {r2.status_code}")
print("Borsa Italiana snippet:")
print(r2.text[:1000])
