import sqlite3
from datetime import date

import pytest

from mcp_server.server import (
    _connect_readonly,
    fetch_article,
    search_articles,
)
from news_collector.db import Database
from news_collector.models import Article

TODAY = date(2026, 10, 31)


def make_article(
    n,
    title=None,
    summary="要約",
    source="zenn:claudecode",
    published_at="2026-10-30T00:00:00+00:00",
):
    return Article(
        source=source,
        title=title if title is not None else f"記事{n}",
        url=f"https://example.com/{n}",
        published_at=published_at,
        summary=summary,
    )


def make_db(tmp_path, articles):
    path = tmp_path / "news.db"
    with Database(path) as db:
        db.save(articles)
    return path


def search(path, **kwargs):
    params = dict(keyword=None, since=None, until=None, source=None, today=TODAY)
    params.update(kwargs)
    return search_articles(path, **params)


def titles(results):
    return [r["title"] for r in results]


def test_returns_newest_first_without_filters(tmp_path):
    path = make_db(
        tmp_path,
        [
            make_article(1, published_at="2026-10-28T00:00:00+00:00"),
            make_article(2, published_at="2026-10-30T00:00:00+00:00"),
            make_article(3, published_at="2026-10-29T00:00:00+00:00"),
        ],
    )

    results = search(path)

    assert titles(results) == ["記事2", "記事3", "記事1"]
    assert set(results[0]) == {"id", "title", "source", "published_at", "url"}


def test_limits_to_10_results(tmp_path):
    path = make_db(tmp_path, [make_article(n) for n in range(12)])

    assert len(search(path)) == 10


def test_keyword_matches_title_or_summary(tmp_path):
    path = make_db(
        tmp_path,
        [
            make_article(1, title="Claude Code 入門", summary="x"),
            make_article(2, title="別の話", summary="Claude Code の使い方"),
            make_article(3, title="関係なし", summary="y"),
        ],
    )

    assert sorted(titles(search(path, keyword="Claude Code"))) == ["Claude Code 入門", "別の話"]


def test_keyword_treats_percent_and_underscore_literally(tmp_path):
    path = make_db(
        tmp_path,
        [
            make_article(1, title="100% 完全"),
            make_article(2, title="1000"),
            make_article(3, title="a_b"),
            make_article(4, title="axb"),
        ],
    )

    assert titles(search(path, keyword="100%")) == ["100% 完全"]
    assert titles(search(path, keyword="a_b")) == ["a_b"]


def test_empty_keyword_and_source_mean_no_filter(tmp_path):
    path = make_db(tmp_path, [make_article(1), make_article(2, source="qiita:ClaudeCode")])

    assert len(search(path, keyword="", source="")) == 2


def test_source_is_prefix_match_ignoring_case(tmp_path):
    path = make_db(
        tmp_path,
        [make_article(1, source="zenn:claudecode"), make_article(2, source="qiita:ClaudeCode")],
    )

    results = search(path, source="Zenn")

    assert [r["source"] for r in results] == ["zenn:claudecode"]


def test_since_and_until_use_japan_time(tmp_path):
    path = make_db(
        tmp_path,
        [
            make_article(1, title="JST 10/31 00:30", published_at="2026-10-30T15:30:00+00:00"),
            make_article(2, title="JST 10/31 23:59:59", published_at="2026-10-31T14:59:59+00:00"),
            make_article(3, title="JST 11/01 00:00", published_at="2026-10-31T15:00:00+00:00"),
        ],
    )

    on_31st = search(path, since="2026-10-31", until="2026-10-31")
    assert sorted(titles(on_31st)) == ["JST 10/31 00:30", "JST 10/31 23:59:59"]

    until_30th = search(path, until="2026-10-30")
    assert titles(until_30th) == []


def test_until_defaults_to_today_in_japan(tmp_path):
    path = make_db(
        tmp_path,
        [
            make_article(1, title="今日", published_at="2026-10-31T14:59:59+00:00"),
            make_article(2, title="明日", published_at="2026-10-31T15:00:00+00:00"),
        ],
    )

    assert titles(search(path)) == ["今日"]


def test_null_published_at_excluded_when_dates_given_and_last_otherwise(tmp_path):
    path = make_db(
        tmp_path,
        [
            make_article(1, title="日付なし", published_at=None),
            make_article(2, title="日付あり", published_at="2026-10-30T00:00:00+00:00"),
        ],
    )

    assert titles(search(path)) == ["日付あり", "日付なし"]
    assert titles(search(path, since="2026-10-01")) == ["日付あり"]


@pytest.mark.parametrize("bad", ["先週", "2026-13-40", "2026/10/31"])
def test_invalid_date_raises_value_error(tmp_path, bad):
    path = make_db(tmp_path, [make_article(1)])

    with pytest.raises(ValueError, match=bad):
        search(path, since=bad)
    with pytest.raises(ValueError, match=bad):
        search(path, until=bad)


def test_since_after_until_raises_value_error(tmp_path):
    path = make_db(tmp_path, [make_article(1)])

    with pytest.raises(ValueError, match="2026-10-31"):
        search(path, since="2026-10-31", until="2026-10-30")


def test_fetch_article_returns_all_fields_or_none(tmp_path):
    path = make_db(tmp_path, [make_article(1, title="本文なし", summary="詳しい要約")])
    article_id = search(path)[0]["id"]

    assert fetch_article(path, article_id) == {
        "id": article_id,
        "source": "zenn:claudecode",
        "title": "本文なし",
        "url": "https://example.com/1",
        "published_at": "2026-10-30T00:00:00+00:00",
        "summary": "詳しい要約",
    }
    assert fetch_article(path, article_id + 100) is None


def test_connect_readonly_does_not_create_missing_db(tmp_path):
    missing = tmp_path / "なし" / "news.db"

    with pytest.raises(sqlite3.OperationalError):
        _connect_readonly(missing)

    assert not missing.exists()
