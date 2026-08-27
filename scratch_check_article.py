from monitor import stage_public_ticker_gate

file_path = "/home/antoinebarbara/.gemini/antigravity/brain/f8b8fe82-82ec-49b5-a3c9-aa20306473b7/.system_generated/steps/190/content.md"
with open(file_path, "r", encoding="utf-8") as f:
    text = f.read()
    
article = {"body": text, "headline": ""}
passed, reason = stage_public_ticker_gate(article, {})
print(f"Passed: {passed}, Reason: {reason}")
if passed:
    print(f"Ticker Match: {article.get('_ticker_match')}")
    print(f"Ticker Match Type: {article.get('_ticker_match_type')}")
    print(f"Deterministic Ticker: {article.get('_deterministic_ticker')}")
