from src.database import (
    initialise_database,
    article_exists,
    save_article,
    article_count,
)

from src.rss import get_rss_entries
from src.prnewswire_parser import download_article
from src.sheets import load_rules
from src.rules_engine import evaluate

SHEET_URL = "https://docs.google.com/spreadsheets/d/1YDOyc8WReBei-7LKPLiXZtmOGCmoY7zuyTvyfMHeL4E/edit#gid=0"

print("=== Special Situations Radar v0.9.0 ===")

initialise_database()

playbooks = load_rules(SHEET_URL)

print(f"[PLAYBOOKS] {len(playbooks)} loaded")

entries = get_rss_entries()

print(f"[RSS] {len(entries)} articles received.")

new_articles = 0

for entry in entries:

    article_id = entry.link.rstrip("/").split("-")[-1].replace(".html", "")
    article_key = f"prnewswire:{article_id}"

    # Temporary: always reprocess articles while testing
    if False and article_exists(article_key):
        continue

    print(f"[DOWNLOAD] {entry.title}")

    body = download_article(entry.link)

    if body is None:
        print("[WARNING] Could not extract article body.")
        continue

    matches = evaluate(body, playbooks)

    if matches:

        print("\n" + "=" * 70)
        print("[MATCH FOUND]")
        print(entry.title)

        for match in matches:
            print(
                f"Playbook: {match['Rule ID']} | {match['Category']}"
            )

        print("=" * 70 + "\n")

    save_article(
        source="prnewswire",
        article_id=article_id,
        title=entry.title,
        url=entry.link,
        published=getattr(entry, "published", ""),
        body=body,
    )

    new_articles += 1

print(f"[DATABASE] {new_articles} new articles stored.")
print(f"[DATABASE] Total articles: {article_count()}")
