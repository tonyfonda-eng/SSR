import requests
import json

url = "https://www.londonstockexchange.com/news?tab=news-explorer&excludeheadlines=&headlinetypes=&headlines=151,33,32,37,36,35,34,144,155,154"
headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
}
response = requests.get(url, headers=headers)
html = response.text
print("Has componentId?", "componentId" in html)
print("Has block_content?", "block_content" in html)
