import requests
from bs4 import BeautifulSoup

BASE_URL = "https://www.investegate.co.uk"
headers = {"User-Agent": "Mozilla/5.0"}
articles = []
response = requests.get(BASE_URL, headers=headers, timeout=15)
soup = BeautifulSoup(response.text, "html.parser")

links = soup.find_all('a', href=True)
seen = set()
for link in links:
    href = link['href']
    if '/announcement/' in href and '/announcement-archive' not in href:
        url = href if href.startswith('http') else f"{BASE_URL}{href}"
        article_id = href.split('/')[-1]
        
        # Try to find a better title by going up the DOM
        parent = link.parent
        title_text = link.get_text(strip=True)
        if not title_text:
            # Maybe inside an h3 or strong?
            title_text = parent.get_text(strip=True)
        
        if article_id not in seen:
            seen.add(article_id)
            articles.append((article_id, title_text, url))
            
print(articles[:3])

if articles:
    url = articles[0][2]
    r = requests.get(url, headers=headers)
    soup2 = BeautifulSoup(r.text, 'html.parser')
    main_container = soup2.find('div', id='announcementContent') or soup2.find('div', class_='container')
    print("Body length:", len(main_container.get_text(separator="\n", strip=True)) if main_container else "No body container")
