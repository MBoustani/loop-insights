import json
import os
import sqlite3
import time

DB_PATH = os.environ.get("DB_PATH", "queries.sqlite3")
MAX_AGE_SECONDS = 3600  # reuse saved data for 1 hour


def connect():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS queries (
            repo TEXT,
            since TEXT,
            until TEXT,
            saved_at REAL,
            data TEXT,
            PRIMARY KEY (repo, since, until)
        )
    """)
    return conn


def find(repo, since, until):
    conn = connect()
    row = conn.execute(
        "SELECT data, saved_at FROM queries WHERE repo = ? AND since = ? AND until = ?",
        (repo, str(since), str(until)),
    ).fetchone()
    conn.close()

    if row and time.time() - row[1] < MAX_AGE_SECONDS:
        return json.loads(row[0])
    return None


def save(repo, since, until, data):
    conn = connect()
    conn.execute(
        "INSERT OR REPLACE INTO queries VALUES (?, ?, ?, ?, ?)",
        (repo, str(since), str(until), time.time(), json.dumps(data)),
    )
    conn.commit()
    conn.close()


def history(limit=20):
    conn = connect()
    rows = conn.execute(
        "SELECT repo, since, until, saved_at FROM queries ORDER BY saved_at DESC LIMIT ?", (limit,)
    ).fetchall()
    conn.close()
    return [{"repo": repo, "since": since, "until": until, "saved_at": saved_at} for repo, since, until, saved_at in rows]
