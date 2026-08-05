import requests
from bs4 import BeautifulSoup
from src.config import USER_AGENT
headers = {"User-Agent": USER_AGENT}
r = requests.get("https://www.prnewswire.com/news-releases/news-releases-list/?page=1&pagesize=10", headers=headers)
soup = BeautifulSoup(r.text, "html.parser")
links = soup.select('.news-release') or soup.select('.card h3 a') or soup.select('.row.newsCards a')
if links:
    print(links[0].prettify())
