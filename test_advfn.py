import requests

url = "https://uk.advfn.com/stock-market/london/news"
headers = {"User-Agent": "Mozilla/5.0"}
try:
    r = requests.get(url, headers=headers)
    print("ADVFN Status:", r.status_code)
    if r.status_code == 200:
        print("Success, length:", len(r.text))
except Exception as e:
    print(e)
