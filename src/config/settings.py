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
    Returns default or environment-configured settings.
    Required by the AI inference modules.
    """
    return {
        "RULE_THRESHOLD": 10,
        "MATERIAL_KEYWORDS": "bump, increase, amend, terminate, cancel, regulatory approval, revised, superior proposal, competing, blocked",
        "Dashboard Publish Interval": 60
    }