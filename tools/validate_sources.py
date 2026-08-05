"""
Standalone diagnostic: tests every active Source URL directly, without running
the full pipeline, to find which ones are genuine RSS/Atom feeds vs which ones
fall back to raw-HTML scraping (and will therefore just re-ingest the same
static page every run).

Usage:
    python3 tools/validate_sources.py

Requires the same GOOGLE_SERVICE_ACCOUNT_JSON env var as the main pipeline, so
it can read the live Sources sheet. Read-only — never modifies the sheet, the
database, or sends alerts.
"""
import sys
import feedparser
import requests
from bs4 import BeautifulSoup

sys.path.insert(0, ".")
from src.sheets import load_sources
from src.config.settings import SHEET_URL


def main():
    sources = load_sources(SHEET_URL)
    active = [s for s in sources if str(s.get("Active", "TRUE")).upper() == "TRUE"]
    print(f"Checking {len(active)} active sources...\n")

    good, fallback, dead = [], [], []

    for source in active:
        name = source.get("Source Name", source.get("Source", "Unknown"))
        url = source.get("URL", source.get("HTML URL", ""))
        if not url:
            print(f"[SKIP]     {name}: no URL configured")
            continue

        try:
            feed = feedparser.parse(url)
            if feed.entries:
                print(f"[OK]       {name:<40} {len(feed.entries)} entries via RSS/Atom  ({url})")
                good.append(name)
                continue
        except Exception:
            pass

        try:
            headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"}
            resp = requests.get(url, headers=headers, timeout=10)
            if resp.status_code == 200:
                soup = BeautifulSoup(resp.text, "html.parser")
                title = soup.title.string.strip() if soup.title and soup.title.string else "(no title)"
                print(f"[FALLBACK] {name:<40} no feed found, HTML fallback -> page title: '{title}'  ({url})")
                fallback.append((name, url, title))
            else:
                print(f"[DEAD]     {name:<40} HTTP {resp.status_code}  ({url})")
                dead.append(name)
        except Exception as e:
            print(f"[DEAD]     {name:<40} {type(e).__name__}: {e}  ({url})")
            dead.append(name)

    print("\n--- SUMMARY ---")
    print(f"Real RSS/Atom feeds : {len(good)}")
    print(f"HTML fallback mode  : {len(fallback)}  <- need a corrected feed URL in the Sources sheet")
    print(f"Unreachable/dead    : {len(dead)}")

    if fallback:
        print("\nSources needing a real feed URL:")
        for name, url, title in fallback:
            print(f"  - {name}  (currently: {url} -> '{title}')")


if __name__ == "__main__":
    main()