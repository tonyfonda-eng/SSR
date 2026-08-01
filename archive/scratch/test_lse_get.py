import requests

url = "https://api.londonstockexchange.com/api/v1/components/refresh?path=news-explorer&parameters=headlines%3D151%2C33%2C32%2C37%2C36%2C35%2C34%2C144%2C155%2C154"
headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "application/json"
}
try:
    r = requests.get(url, headers=headers)
    print("Status:", r.status_code)
    print(r.text[:500])
except Exception as e:
    print(e)
