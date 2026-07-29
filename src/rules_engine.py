"""
Investment playbook engine.
"""


def evaluate(article_text, playbooks):
    matches = []

    text = article_text.lower()

    for playbook in playbooks:

        if playbook.get("Enabled", "").upper() != "TRUE":
            continue

        passed = True

        # 1. Process Required OR conditions
        for key, value in playbook.items():
            if key.startswith("Required_") and key.endswith("_OR"):
                val = str(value).strip()
                if not val:
                    continue
                
                options = [x.strip().strip('"').lower() for x in val.split("|")]
                if not any(option in text for option in options if option):
                    passed = False
                    break
        
        if not passed:
            continue

        # 2. Process Exclusions NOT conditions
        exclusions_raw = str(playbook.get("Exclusions_NOT", "")).strip()
        if exclusions_raw:
            exclusions = [x.strip().strip('"').lower() for x in exclusions_raw.split("|")]
            if any(exc in text for exc in exclusions if exc):
                passed = False
                
        if passed:
            # Include confidence modifier for downstream processing
            conf_mod = str(playbook.get("Confidence_Modifier", "")).strip()
            if conf_mod:
                playbook["_Confidence_Modifier"] = conf_mod
            matches.append(playbook)

    return matches
