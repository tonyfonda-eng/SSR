import requests
import json

url = "https://www.londonstockexchange.com/news?tab=news-explorer&excludeheadlines=&headlinetypes=&headlines=151,33,32,37,36,35,34,144,155,154"
headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
}
response = requests.get(url, headers=headers)
print("Status:", response.status_code)
html = response.text
if "window.__INITIAL_STATE__" in html:
    print("Found INITIAL_STATE")
elif "ng-server-context" in html:
    print("Angular SSR")
