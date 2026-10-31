import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from news_collector.models import Article

_SCHEMA = """
CREATE TABLE IF NOT EXISTS articles (
    id           INTEGER PRIMARY KEY,
    url          TEXT NOT NULL UNIQUE,
    source       TEXT NOT NULL,
    title        TEXT NOT NULL,
    published_at TEXT,
    summary      TEXT NOT NULL,
    fetched_at   TEXT NOT NULL
)
"""


class Database:
    def __init__(self, path):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(path)
        self._conn.execute(_SCHEMA)
        self._conn.commit()

    def save(self, articles: list[Article]) -> int:
        """新しい記事だけ保存し、実際に追加した件数を返す。URL が同じ記事は無視する。"""
        fetched_at = datetime.now(UTC).isoformat(timespec="seconds")
        added = 0
        with self._conn:
            for article in articles:
                cursor = self._conn.execute(
                    "INSERT OR IGNORE INTO articles"
                    " (url, source, title, published_at, summary, fetched_at)"
                    " VALUES (?, ?, ?, ?, ?, ?)",
                    (
                        article.url,
                        article.source,
                        article.title,
                        article.published_at,
                        article.summary,
                        fetched_at,
                    ),
                )
                added += cursor.rowcount
        return added

    def close(self):
        self._conn.close()

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        self.close()
