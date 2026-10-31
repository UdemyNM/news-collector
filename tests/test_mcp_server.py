import pytest
from mcp import Client

from mcp_server.server import create_server
from news_collector.db import Database
from news_collector.models import Article


def make_article(n, title=None, summary="要約", source="zenn:claudecode", published_at=None):
    return Article(
        source=source,
        title=title or f"記事{n}",
        url=f"https://example.com/{n}",
        published_at=published_at or f"2026-10-{10 + n:02d}T00:00:00+00:00",
        summary=summary,
    )


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
def db_path(tmp_path):
    path = tmp_path / "news.db"
    with Database(path) as db:
        db.save(
            [
                make_article(1, title="Claude Code 入門", summary="詳しい要約"),
                make_article(2, title="Qiita の話", source="qiita:ClaudeCode"),
                make_article(3, title="新しい記事"),
            ]
        )
    return path


@pytest.fixture
async def client(db_path):
    async with Client(create_server(db_path), raise_exceptions=True) as c:
        yield c


@pytest.mark.anyio
async def test_lists_two_tools(client):
    tools = {t.name: t for t in (await client.list_tools()).tools}

    assert set(tools) == {"search_news", "get_article"}
    assert tools["search_news"].input_schema.get("required", []) == []
    assert tools["get_article"].input_schema["required"] == ["id"]


@pytest.mark.anyio
async def test_search_news_returns_structured_results(client):
    result = await client.call_tool("search_news", {"keyword": "Claude Code", "source": "zenn"})

    assert result.is_error is False
    items = result.structured_content["result"]
    assert [i["title"] for i in items] == ["Claude Code 入門"]
    assert set(items[0]) == {"id", "title", "source", "published_at", "url"}


@pytest.mark.anyio
async def test_search_news_without_arguments_returns_recent_first(client):
    result = await client.call_tool("search_news", {})

    assert result.is_error is False
    titles = [i["title"] for i in result.structured_content["result"]]
    assert titles == ["新しい記事", "Qiita の話", "Claude Code 入門"]


@pytest.mark.anyio
async def test_search_news_invalid_date_is_tool_error(client):
    result = await client.call_tool("search_news", {"since": "先週"})

    assert result.is_error is True
    assert "先週" in result.content[0].text


@pytest.mark.anyio
async def test_search_news_since_after_until_is_tool_error(client):
    result = await client.call_tool(
        "search_news", {"since": "2026-10-31", "until": "2026-10-30"}
    )

    assert result.is_error is True
    assert "2026-10-31" in result.content[0].text


@pytest.mark.anyio
async def test_get_article_returns_all_fields(client):
    found = await client.call_tool("search_news", {"keyword": "入門"})
    article_id = found.structured_content["result"][0]["id"]

    result = await client.call_tool("get_article", {"id": article_id})

    assert result.is_error is False
    assert result.structured_content == {
        "id": article_id,
        "source": "zenn:claudecode",
        "title": "Claude Code 入門",
        "url": "https://example.com/1",
        "published_at": "2026-10-11T00:00:00+00:00",
        "summary": "詳しい要約",
    }


@pytest.mark.anyio
async def test_get_article_unknown_id_is_tool_error(client):
    result = await client.call_tool("get_article", {"id": 9999})

    assert result.is_error is True
    assert "見つかりません" in result.content[0].text


@pytest.mark.anyio
async def test_missing_db_is_tool_error_and_not_created(tmp_path):
    missing = tmp_path / "news.db"

    async with Client(create_server(missing), raise_exceptions=True) as client:
        result = await client.call_tool("search_news", {})

    assert result.is_error is True
    assert "news-collector" in result.content[0].text
    assert not missing.exists()
