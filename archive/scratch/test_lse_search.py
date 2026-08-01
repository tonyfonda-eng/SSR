import urllib.request
import urllib.parse
import json

url = "https://api.londonstockexchange.com/api/v1/components/refresh"
headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
    "Content-Type": "application/json"
}
payload = {
    "path": "news",
    "parameters": "tab=news-explorer&excludeheadlines=&headlinetypes=&headlines=151,33,32,37,36,35,34,144,155,154",
    "components": [
        {
            "componentId": "block_content-43191-Zq5xUu4k",
            "parameters": "tab=news-explorer&excludeheadlines=&headlinetypes=&headlines=151,33,32,37,36,35,34,144,155,154"
        }
    ]
}
req = urllib.request.Request(url, data=json.dumps(payload).encode('utf-8'), headers=headers, method='POST')
try:
    response = urllib.request.urlopen(req)
    print(response.read().decode('utf-8')[:500])
except Exception as e:
    print("Error:", e)
