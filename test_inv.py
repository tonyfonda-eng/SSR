import requests
headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36"}
try:
    r = requests.get("https://www.investegate.co.uk/", headers=headers)
    print("investegate / status:", r.status_code)
    r2 = requests.get("https://www.investegate.co.uk/company-announcements", headers=headers)
    print("investegate /company-announcements status:", r2.status_code)
except Exception as e:
    print(e)
