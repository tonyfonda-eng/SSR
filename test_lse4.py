import requests

url = "https://api.londonstockexchange.com/api/gw/lse/news?page=0&size=20&tabId=news-explorer&headlines=151,33,32,37,36,35,34,144,155,154"
headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
}
try:
    r = requests.get(url, headers=headers)
    print("GET Status:", r.status_code)
    if r.status_code == 200:
        print(r.text[:500])
except Exception as e:
    print(e)
