"""ためたニュース記事を Claude から検索する MCP サーバー（stdio）。"""

import sqlite3
from datetime import UTC, date, datetime, time, timedelta, timezone
from pathlib import Path
from typing import TypedDict

from mcp.server import MCPServer
from mcp.server.mcpserver.exceptions import ToolError

from news_collector.config import load_config

CONFIG_PATH = Path(__file__).resolve().parent.parent / "config.toml"
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


def create_server(db_path: Path) -> MCPServer:
    """db_path の記事 DB を検索するサーバーを作る。DB は呼び出しのたびに開く。"""
    server = MCPServer("news-collector")

    @server.tool()
    def search_news(
        keyword: str | None = None,
        since: str | None = None,
        until: str | None = None,
        source: str | None = None,
    ) -> list[ArticleSummary]:
        """ためた技術ニュース記事（Zenn / Qiita / GitHub Releases）を検索する。引数はすべて省略できる。

        結果は公開日時の新しい順で、最大 10 件。要約は含まないので、中身を知りたい記事は
        get_article で id を指定して取り出すこと。

        keyword: タイトルまたは要約に含まれる文字列（部分一致）。
        since / until: 公開日の範囲。YYYY-MM-DD 形式の日本時間の日付で、両端を含む。
            「先週」などの言い方は、呼ぶ側で具体的な日付に直して渡すこと。
            until を省略すると今日まで。
        source: 出どころの先頭の文字列。zenn / qiita / github など（大文字小文字は区別しない）。
        """
        today = datetime.now(JST).date()
        try:
            return search_articles(
                db_path, keyword=keyword, since=since, until=until, source=source, today=today
            )
        except ValueError as e:
            raise ToolError(str(e)) from None
        except sqlite3.OperationalError:
            raise ToolError(_DB_UNAVAILABLE) from None

    @server.tool()
    def get_article(id: int) -> ArticleDetail:
        """記事を 1 件、id で取り出す。id は search_news の結果にあるものを渡す。"""
        try:
            article = fetch_article(db_path, id)
        except sqlite3.OperationalError:
            raise ToolError(_DB_UNAVAILABLE) from None
        if article is None:
            raise ToolError(f"id={id} の記事は見つかりません")
        return article

    return server


_DB_UNAVAILABLE = "記事 DB を開けません。先に news-collector を実行して記事を集めてください"

mcp = create_server(load_config(CONFIG_PATH).db_path)

if __name__ == "__main__":
    mcp.run()
