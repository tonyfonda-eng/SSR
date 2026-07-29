import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.article import download_article

URL = "https://www.prnewswire.com/news-releases/tencent-brings-together-ai-and-games-to-help-preserve-and-share-cultural-heritage-of-new-unesco-site-in-jingdezhen-302834555.html"
print("=" * 60)
print("Testing PR Newswire parser")
print("=" * 60)

body = download_article(URL)

if body is None:
    print("❌ Parser failed")
else:
    print("✅ Parser succeeded")
    print(f"Characters extracted: {len(body):,}")
    print()
    print(body[:1000])
