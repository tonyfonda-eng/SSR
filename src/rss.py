"""
RSS reader for PR Newswire
"""

import feedparser
from src.config import RSS_FEED


def get_rss_entries():
    feed = feedparser.parse(RSS_FEED)
    return feed.entries
