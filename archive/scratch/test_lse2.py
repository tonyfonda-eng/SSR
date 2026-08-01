import requests
import re

url = "https://www.londonstockexchange.com/news?tab=news-explorer&excludeheadlines=&headlinetypes=&headlines=151,33,32,37,36,35,34,144,155,154"
headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36"
}
response = requests.get(url, headers=headers)
html = response.text

# Look for api endpoints
endpoints = set(re.findall(r'https?://[^\s\"\'\>]+api\.londonstockexchange\.com[^\s\"\'\>]*', html))
print("Endpoints found:", endpoints)

# Look for json configs
if "api.londonstockexchange.com" in html:
    print("Found API domain in HTML")
