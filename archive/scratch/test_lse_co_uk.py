import requests
import feedparser

headers = {"User-Agent": "Mozilla/5.0"}
url = "https://www.lse.co.uk/news/"
response = requests.get(url, headers=headers)
print("lse.co.uk Status:", response.status_code)
if response.status_code == 200:
    print(response.text[:200])
