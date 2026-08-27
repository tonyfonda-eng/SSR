import re
file_path = "/home/antoinebarbara/.gemini/antigravity/brain/f8b8fe82-82ec-49b5-a3c9-aa20306473b7/.system_generated/steps/190/content.md"
with open(file_path, "r", encoding="utf-8") as f:
    text = f.read()

match = re.search(r'\b(?:NYSE|NASDAQ|AMEX|OTC|TSX|LSE|NYSE MKT|NYSE ARCA)\s*[:]\s*([A-Z]{1,5})\b', text, re.IGNORECASE)
if not match:
    match = re.search(r'\((?:NYSE|NASDAQ|AMEX|OTC|TSX|LSE)\s*:\s*([A-Z]{1,5})\)', text, re.IGNORECASE)
print("Old logic match:", match.group(0) if match else "None")
