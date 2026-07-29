#!/bin/bash

# Network Notification Credentials
export SSR_SMTP_HOST="smtp.gmail.com"
export SSR_SMTP_PORT="587"
export SSR_SMTP_USER="karimbarbara7@gmail.com"
export SSR_SMTP_PASSWORD="htxrgxfstxkpzpvv"
export SSR_SMTP_SENDER="karimbarbara7@gmail.com"
export SSR_SMTP_RECIPIENT="karimbarbara7@gmail.com"

# Operational Cockpit
export SSR_SPREADSHEET_ID="1R27iguAnAaiwJT8qfNco8tj2dNgbxIB7jVW_OJw7wQY"

# Execute Replay
PYTHONPATH=. python3 replay.py "ssr_cache/sec/2026/07/accession-number=0001140361-26-029775_5d3062.html"
^\
