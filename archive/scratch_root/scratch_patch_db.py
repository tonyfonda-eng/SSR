import re

with open('src/database.py', 'r') as f:
    content = f.read()

# 1. Add _get_connection function
helper_code = """
def _get_connection(db_path: str):
    conn = sqlite3.connect(db_path, timeout=30.0)
    # Ensure WAL mode is active for concurrency
    conn.execute("PRAGMA journal_mode = WAL;")
    conn.execute("PRAGMA synchronous = NORMAL;")
    return conn
"""

content = content.replace("DB_PATH = RESEARCH_DB_PATH\n", "DB_PATH = RESEARCH_DB_PATH\n" + helper_code)

# 2. Replace all sqlite3.connect with _get_connection
content = re.sub(r"sqlite3\.connect\(([^)]+)\)", r"_get_connection(\1)", content)

with open('src/database.py', 'w') as f:
    f.write(content)

