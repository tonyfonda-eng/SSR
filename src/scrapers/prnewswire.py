"""
Downloads and extracts PR Newswire articles.
"""

import requests
from bs4 import BeautifulSoup

from src.config import USER_AGENT


def download_article(url):

    headers = {
        "User-Agent": USER_AGENT
    }

    response = requests.get(
        url,
        headers=headers,
        timeout=30,
    )

    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")

    # Try several possible article containers
    selectors = [
        "div.release-body",
        "div.release-text",
        "div.article-body",
        "div[data-module='ArticleBody']",
        "article",
        "main",
    ]

    for selector in selectors:

        article = soup.select_one(selector)

        if article:

            text = article.get_text("\n", strip=True)

            # Ignore obviously bad extractions
            if len(text) > 1000:
                return text

    return None
