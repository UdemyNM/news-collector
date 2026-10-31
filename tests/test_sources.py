import json

import httpx
import pytest

from news_collector.config import SourceConfig
from news_collector.models import Article
from news_collector.sources import FetchError, fetch_articles
from sample_data import QIITA_ATOM, ZENN_RSS, github_release


def make_client(handler):
    return httpx.Client(transport=httpx.MockTransport(handler))


def respond(requests, response):
    """リクエストを記録しつつ、固定のレスポンスを返すハンドラを作る。"""

    def handler(request):
        requests.append(str(request.url))
        return response

    return handler


def test_zenn_requests_the_topic_feed_and_maps_items_to_articles():
    requests = []
    client = make_client(respond(requests, httpx.Response(200, text=ZENN_RSS)))

    articles = fetch_articles(client, SourceConfig(type="zenn", target="claudecode"))

    assert requests == ["https://zenn.dev/topics/claudecode/feed"]
    assert articles == [
        Article(
            source="zenn:claudecode",
            title="Claude Code入門",
            url="https://zenn.dev/alice/articles/aaa111",
            published_at="2026-10-31T09:21:22+00:00",
            summary="はじめに：最初の要約です",
        ),
        Article(
            source="zenn:claudecode",
            title="フック活用術",
            url="https://zenn.dev/bob/articles/bbb222",
            published_at="2026-10-30T00:00:00+00:00",
            summary="二番目の要約",
        ),
    ]


def test_qiita_requests_the_tag_feed_and_normalizes_published_to_utc():
    requests = []
    client = make_client(respond(requests, httpx.Response(200, text=QIITA_ATOM)))

    articles = fetch_articles(client, SourceConfig(type="qiita", target="ClaudeCode"))

    assert requests == ["https://qiita.com/tags/ClaudeCode/feed"]
    assert articles == [
        Article(
            source="qiita:ClaudeCode",
            title="Qiitaの記事",
            url="https://qiita.com/carol/items/ccc333",
            published_at="2026-10-31T09:47:11+00:00",  # 18:47 +09:00 を UTC に直した値
            summary="Qiitaの本文の冒頭",
        )
    ]


def test_github_releases_requests_the_api_and_maps_releases_to_articles():
    requests = []
    payload = [github_release()]
    client = make_client(respond(requests, httpx.Response(200, json=payload)))

    articles = fetch_articles(
        client, SourceConfig(type="github_releases", target="anthropics/claude-code")
    )

    assert requests == ["https://api.github.com/repos/anthropics/claude-code/releases"]
    assert articles == [
        Article(
            source="github:anthropics/claude-code",
            title="v2.1.316",
            url="https://github.com/anthropics/claude-code/releases/tag/v2.1.316",
            published_at="2026-10-31T01:01:35+00:00",
            summary="## What's changed\n\n- Added a flag",
        )
    ]


def test_github_release_without_a_name_falls_back_to_the_tag_name():
    payload = [github_release(name="", tag_name="v9.9.9")]
    client = make_client(respond([], httpx.Response(200, json=payload)))

    articles = fetch_articles(
        client, SourceConfig(type="github_releases", target="anthropics/claude-code")
    )

    assert articles[0].title == "v9.9.9"


def test_github_release_with_null_body_gets_an_empty_summary():
    payload = [github_release(body=None)]
    client = make_client(respond([], httpx.Response(200, json=payload)))

    articles = fetch_articles(
        client, SourceConfig(type="github_releases", target="anthropics/claude-code")
    )

    assert articles[0].summary == ""


def test_long_summaries_are_cut_to_300_characters():
    payload = [github_release(body="あ" * 1000)]
    client = make_client(respond([], httpx.Response(200, json=payload)))

    articles = fetch_articles(
        client, SourceConfig(type="github_releases", target="anthropics/claude-code")
    )

    assert articles[0].summary == "あ" * 300


@pytest.mark.parametrize(
    "source",
    [
        SourceConfig(type="zenn", target="claudecode"),
        SourceConfig(type="qiita", target="ClaudeCode"),
        SourceConfig(type="github_releases", target="anthropics/claude-code"),
    ],
)
def test_http_error_status_raises(source):
    client = make_client(respond([], httpx.Response(500, text="boom")))

    with pytest.raises(httpx.HTTPStatusError):
        fetch_articles(client, source)


@pytest.mark.parametrize("source_type", ["zenn", "qiita"])
def test_feed_source_returning_html_instead_of_a_feed_raises_fetch_error(source_type):
    html = "<html><body>メンテナンス中</body></html>"
    client = make_client(respond([], httpx.Response(200, text=html)))

    with pytest.raises(FetchError):
        fetch_articles(client, SourceConfig(type=source_type, target="x"))


def test_valid_feed_with_no_entries_returns_an_empty_list():
    empty_rss = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<rss version="2.0"><channel><title>t</title></channel></rss>'
    )
    client = make_client(respond([], httpx.Response(200, text=empty_rss)))

    articles = fetch_articles(client, SourceConfig(type="zenn", target="claudecode"))

    assert articles == []


def test_github_response_that_is_not_a_list_raises_fetch_error():
    body = json.dumps({"message": "unexpected"})
    client = make_client(respond([], httpx.Response(200, text=body)))

    with pytest.raises(FetchError):
        fetch_articles(
            client, SourceConfig(type="github_releases", target="anthropics/claude-code")
        )
