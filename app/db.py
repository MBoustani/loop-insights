import json
import os
import sqlite3
import time

DB_PATH = os.environ.get("DB_PATH", "queries.sqlite3")
MAX_AGE_SECONDS = 3600  # reuse saved data for 1 hour


def connect():
    conn = sqlite3.connect(DB_PATH, timeout=10)  # wait if another request is writing
    conn.execute("""
        CREATE TABLE IF NOT EXISTS cache (
            kind TEXT,
            repo TEXT,
            since TEXT,
            until TEXT,
            saved_at REAL,
            data TEXT,
            PRIMARY KEY (kind, repo, since, until)
        )
    """)
    return conn


# kind says what is saved: "github" for GitHub data, "narrative:<model>" for LLM answers
def find(kind, repo, since, until):
    conn = connect()
    row = conn.execute(
        "SELECT data, saved_at FROM cache WHERE kind = ? AND repo = ? AND since = ? AND until = ?",
        (kind, repo, str(since), str(until)),
    ).fetchone()
    conn.close()

    if row and time.time() - row[1] < MAX_AGE_SECONDS:
        return json.loads(row[0])
    return None


def save(kind, repo, since, until, data):
    conn = connect()
    conn.execute(
        "INSERT OR REPLACE INTO cache VALUES (?, ?, ?, ?, ?, ?)",
        (kind, repo, str(since), str(until), time.time(), json.dumps(data)),
    )
    conn.commit()
    conn.close()


def history(limit=20):
    conn = connect()
    rows = conn.execute(
        "SELECT repo, since, until, saved_at FROM cache WHERE kind = 'github' ORDER BY saved_at DESC LIMIT ?",
        (limit,),
    ).fetchall()
    conn.close()
    return [{"repo": repo, "since": since, "until": until, "saved_at": saved_at} for repo, since, until, saved_at in rows]
