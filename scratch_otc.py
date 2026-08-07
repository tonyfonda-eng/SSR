from curl_cffi import requests
url = "https://backend.otcmarkets.com/bussvc/news/summary?page=1&pageSize=50"
headers = {
    'Accept': 'application/json, text/plain, */*',
    'Origin': 'https://www.otcmarkets.com',
    'Referer': 'https://www.otcmarkets.com/',
}
response = requests.get(url, headers=headers, impersonate="chrome120", timeout=10)
print(response.status_code)
