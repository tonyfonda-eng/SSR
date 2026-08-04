"""
Special Situations Radar
Configuration
"""
import os

SHEET_URL = "https://docs.google.com/spreadsheets/d/1YDOyc8WReBei-7LKPLiXZtmOGCmoY7zuyTvyfMHeL4E/edit#gid=0"

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 "
    "(KHTML, like Gecko) "
    "Chrome/138.0 Safari/537.36"
)

def get_system_settings(sheet_url=None):
    """
    Returns live system settings from Google Sheets, 
    falling back to robust defaults if unavailable.
    """
    try:
        from src.sheets import get_system_settings as sheets_get_settings
        records = sheets_get_settings(sheet_url or SHEET_URL)
        if records and isinstance(records, list):
            return records[0]
    except Exception:
        pass
        
    return {
        "RULE_THRESHOLD": 10,
        "MATERIAL_KEYWORDS": "bump, increase, amend, terminate, cancel, regulatory approval, revised, superior proposal, competing, blocked",
        "Dashboard Publish Interval": 60
    }