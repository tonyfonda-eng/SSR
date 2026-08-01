from src.html_generator import generate_dashboard_html, generate_archive_html
from src.database import get_recent_lifecycle_logs, export_archive_json
import os

os.makedirs("docs", exist_ok=True)
export_archive_json("docs/archive_data.json")
generate_archive_html("docs/archive.html")
print("Done")
