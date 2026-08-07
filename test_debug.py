import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import hashlib
valid_article = {
    "source": "Valid Source",
    "channel": "HTML",
    "title": "A Valid Title",
    "url": "https://valid.com",
    "published": "",
    "body": "This is a valid body text.",
    "document_type": "Press Release"
}
def validate_article_contract(art):
    required = ["source", "channel", "title", "url", "published", "body", "article_hash"]
    for req in required:
        if req not in art:
            raise KeyError(f"Missing mandatory field: {req}")
    title_text = art.get("title", "").strip().lower()
    source_text = art.get("source", "").strip().lower()
    if not title_text or title_text == "no title" or title_text == "html document":
        title_text = art.get("body", "")[:200].strip().lower()
    art["article_hash"] = hashlib.md5(f"{source_text}::{title_text}".encode('utf-8')).hexdigest()
    return art

try:
    validate_article_contract(valid_article)
    print("Valid succeeded")
except Exception as e:
    print("Valid failed:", e)
