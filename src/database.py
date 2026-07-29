def initialise_database():
    conn = get_connection()

    # 1. Create the table if it is a completely fresh run
    conn.execute("""
        CREATE TABLE IF NOT EXISTS articles (
            article_key TEXT PRIMARY KEY,
            source TEXT NOT NULL,
            article_id TEXT NOT NULL,
            title TEXT,
            url TEXT,
            published TEXT,
            body TEXT,
            processed_at TEXT
        )
    """)

    # 2. Force a schema upgrade if it's loading an old cached database
    try:
        conn.execute("ALTER TABLE articles ADD COLUMN body TEXT")
        print("[DATABASE] Upgraded schema: added 'body' column.")
    except sqlite3.OperationalError:
        # The column already exists, safe to ignore
        pass

    conn.commit()
    conn.close()

    print("[DATABASE] Ready")
