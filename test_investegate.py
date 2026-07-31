import requests
from bs4 import BeautifulSoup
import feedparser

headers = {"User-Agent": "Mozilla/5.0"}
url = "https://www.investegate.co.uk/announcements"
response = requests.get(url, headers=headers)
print("Investegate Status:", response.status_code)
if response.status_code == 200:
    soup = BeautifulSoup(response.text, "html.parser")
    articles = soup.select("a[href*='/announcement/']")
    print("Found articles:", len(articles))
