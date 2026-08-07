import re

with open('src/ingestion/scrapers.py', 'r') as f:
    content = f.read()

# Make orchestrator use checkpoints_to_set if provided
# In scrapers.py, we have:
# if ledger["status"] in ("OK", "EMPTY") and raw_articles and ledger["recovery_status"] in ("NOT_REQUIRED", "RECOVERED"):
#    set_checkpoint(source_name, "HTML", raw_articles[0].get("url") or raw_articles[0].get("id"))

target = """            if ledger["status"] in ("OK", "EMPTY") and raw_articles and ledger["recovery_status"] in ("NOT_REQUIRED", "RECOVERED"):
                if "checkpoints_to_set" in ledger.get("metadata", {}):
                    for src, chnl, val in ledger["metadata"]["checkpoints_to_set"]:
                        set_checkpoint(src, chnl, val)
                    ledger["checkpoint_after"] = "multiple"
                else:
                    set_checkpoint(source_name, "HTML", raw_articles[0].get("url") or raw_articles[0].get("id"))
                    ledger["checkpoint_after"] = raw_articles[0].get("url") or raw_articles[0].get("id")"""

content = content.replace("""            if ledger["status"] in ("OK", "EMPTY") and raw_articles and ledger["recovery_status"] in ("NOT_REQUIRED", "RECOVERED"):
                set_checkpoint(source_name, "HTML", raw_articles[0].get("url") or raw_articles[0].get("id"))
                ledger["checkpoint_after"] = raw_articles[0].get("url") or raw_articles[0].get("id")""", target)

with open('src/ingestion/scrapers.py', 'w') as f:
    f.write(content)


with open('src/scrapers/businesswire.py', 'r') as f:
    bw_content = f.read()

# In businesswire.py, remove set_checkpoint inside the loop and append to list instead
target_bw = """                    if not checkpoint or feed_checkpoint_found:
                        self.scrape_metadata["checkpoints_to_set"].append(("Business Wire", f"RSS-{category_name}", first_id))
                    else:"""

bw_content = bw_content.replace("""                    if not checkpoint or feed_checkpoint_found:
                        set_checkpoint("Business Wire", f"RSS-{category_name}", first_id)
                    else:""", target_bw)

# Add checkpoints_to_set to metadata init
target_init = """        self.scrape_metadata = {
            "source": "Business Wire",
            "mode": "RSS",
            "checkpoint_found": False,
            "recovery_attempted": False,
            "recovery_status": "NOT_REQUIRED",
            "pages_visited": 1,
            "page_limit": 1,
            "emergency_stop": False,
            "reason": "",
            "checkpoints_to_set": []
        }"""
        
bw_content = re.sub(r'self\.scrape_metadata = \{.*?"reason": ""\n        \}', target_init, bw_content, flags=re.DOTALL)

with open('src/scrapers/businesswire.py', 'w') as f:
    f.write(bw_content)
