import requests
from bs4 import BeautifulSoup

headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
r = requests.get("https://www.investegate.co.uk/", headers=headers)
soup = BeautifulSoup(r.text, 'html.parser')

links = soup.find_all('a', href=True)
announcements = [l['href'] for l in links if 'announcement' in l['href']]
print("Announcements found:", len(announcements))
if announcements:
    print(announcements[:5])
