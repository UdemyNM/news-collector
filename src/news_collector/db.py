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

    def average_length(self) -> float:
        """保存済み記事の本文（summary）の平均文字数を返す。"""
        (avg,) = self._conn.execute(
            "SELECT AVG(LENGTH(summary)) FROM articles"
        ).fetchone()
        return avg if avg is not None else 0.0

    def count_articles(self, keyword: str) -> int:
        """タイトルまたは本文（summary）にキーワードを含む記事の件数を返す（部分一致）。"""
        escaped = keyword.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        pattern = f"%{escaped}%"
        (count,) = self._conn.execute(
            "SELECT COUNT(*) FROM articles"
            " WHERE title LIKE ? ESCAPE '\\' OR summary LIKE ? ESCAPE '\\'",
            (pattern, pattern),
        ).fetchone()
        return count

    def count_by_source(self) -> dict[str, int]:
        """出どころ（source 列）ごとの記事件数を返す。記事がなければ空の dict。"""
        rows = self._conn.execute(
            "SELECT source, COUNT(*) FROM articles GROUP BY source ORDER BY source"
        ).fetchall()
        return dict(rows)

    def list_articles(self, source: str | None = None, limit: int = 10) -> list[Article]:
        """公開日時の新しい順に記事を返す（日付なしは最後）。source を指定するとその出どころだけ。"""
        sql = "SELECT source, title, url, published_at, summary FROM articles"
        params: list[str | int] = []
        if source is not None:
            sql += " WHERE source = ?"
            params.append(source)
        sql += " ORDER BY published_at IS NULL, published_at DESC, id DESC LIMIT ?"
        params.append(limit)
        return [Article(*row) for row in self._conn.execute(sql, params).fetchall()]

    def close(self):
        self._conn.close()

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        self.close()
