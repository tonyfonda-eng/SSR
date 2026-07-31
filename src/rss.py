"""
RSS reader for PR Newswire
"""

import feedparser
import requests
from src.config import RSS_FEED


def get_rss_entries():
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        response = requests.get(RSS_FEED, headers=headers, timeout=15)
        response.raise_for_status()
        feed = feedparser.parse(response.content)
    except Exception as e:
        print(f"Error fetching legacy RSS: {e}")
        return []
    
    return feed.entries
