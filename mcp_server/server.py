"""ためたニュース記事を Claude から検索する MCP サーバー（stdio）。"""

import sqlite3
from datetime import UTC, date, datetime, time, timedelta, timezone
from pathlib import Path
from typing import TypedDict

MAX_RESULTS = 10
JST = timezone(timedelta(hours=9))


class ArticleSummary(TypedDict):
    id: int
    title: str
    source: str
    published_at: str | None
    url: str


class ArticleDetail(TypedDict):
    id: int
    source: str
    title: str
    url: str
    published_at: str | None
    summary: str


def _connect_readonly(db_path: Path) -> sqlite3.Connection:
    """DB を読み取り専用で開く。ファイルがなければ作らずに OperationalError にする。"""
    uri = Path(db_path).resolve().as_uri() + "?mode=ro"
    return sqlite3.connect(uri, uri=True)


def _parse_date(name: str, value: str) -> date:
    try:
        if len(value) != 10:
            raise ValueError
        return date.fromisoformat(value)
    except ValueError:
        raise ValueError(
            f"{name} は YYYY-MM-DD 形式の日付で指定してください（受け取った値: {value!r}）"
        ) from None


def _jst_midnight_as_utc(day: date) -> str:
    """日本時間のその日の 0 時を、DB と同じ形式の UTC 文字列にする。"""
    moment = datetime.combine(day, time.min, JST).astimezone(UTC)
    return moment.strftime("%Y-%m-%dT%H:%M:%S+00:00")


def _like_pattern(text: str, *, prefix_only: bool = False) -> str:
    escaped = text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"{escaped}%" if prefix_only else f"%{escaped}%"


def search_articles(
    db_path: Path,
    *,
    keyword: str | None,
    since: str | None,
    until: str | None,
    source: str | None,
    today: date,
) -> list[ArticleSummary]:
    since_day = _parse_date("since", since) if since else None
    until_day = _parse_date("until", until) if until else None
    last_day = until_day or today
    if since_day and since_day > last_day:
        raise ValueError(
            f"since ({since_day.isoformat()}) が until ({last_day.isoformat()}) より後になっています"
        )

    conditions: list[str] = []
    params: list[str | int] = []
    if keyword:
        pattern = _like_pattern(keyword)
        conditions.append("(title LIKE ? ESCAPE '\\' OR summary LIKE ? ESCAPE '\\')")
        params += [pattern, pattern]
    if source:
        conditions.append("source LIKE ? ESCAPE '\\'")
        params.append(_like_pattern(source, prefix_only=True))
    if since_day:
        conditions.append("published_at >= ?")
        params.append(_jst_midnight_as_utc(since_day))
    # until を省略したときは「今日まで」。日付のない記事は、日付で絞っていないので残す。
    until_limit = _jst_midnight_as_utc(last_day + timedelta(days=1))
    if until_day:
        conditions.append("published_at < ?")
    else:
        conditions.append("(published_at IS NULL OR published_at < ?)")
    params.append(until_limit)

    sql = (
        "SELECT id, title, source, published_at, url FROM articles"
        f" WHERE {' AND '.join(conditions)}"
        " ORDER BY published_at DESC, id DESC LIMIT ?"
    )
    params.append(MAX_RESULTS)

    conn = _connect_readonly(db_path)
    try:
        rows = conn.execute(sql, params).fetchall()
    finally:
        conn.close()
    return [
        ArticleSummary(id=r[0], title=r[1], source=r[2], published_at=r[3], url=r[4])
        for r in rows
    ]


def fetch_article(db_path: Path, article_id: int) -> ArticleDetail | None:
    conn = _connect_readonly(db_path)
    try:
        row = conn.execute(
            "SELECT id, source, title, url, published_at, summary FROM articles WHERE id = ?",
            (article_id,),
        ).fetchone()
    finally:
        conn.close()
    if row is None:
        return None
    return ArticleDetail(
        id=row[0],
        source=row[1],
        title=row[2],
        url=row[3],
        published_at=row[4],
        summary=row[5],
    )
