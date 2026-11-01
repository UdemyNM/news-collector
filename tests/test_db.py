import sqlite3

from news_collector.db import Database
from news_collector.models import Article


def make_article(url, title="タイトル", source="zenn:claudecode", summary="要約"):
    return Article(
        source=source,
        title=title,
        url=url,
        published_at="2026-10-31T09:21:22+00:00",
        summary=summary,
    )


def read_rows(path):
    conn = sqlite3.connect(path)
    try:
        return conn.execute(
            "SELECT source, title, url, published_at, summary FROM articles ORDER BY url"
        ).fetchall()
    finally:
        conn.close()


def test_save_stores_articles_and_returns_new_count(tmp_path):
    path = tmp_path / "news.db"
    with Database(path) as db:
        added = db.save(
            [
                make_article("https://example.com/a", title="A"),
                make_article("https://example.com/b", title="B"),
            ]
        )

    assert added == 2
    assert read_rows(path) == [
        ("zenn:claudecode", "A", "https://example.com/a", "2026-10-31T09:21:22+00:00", "要約"),
        ("zenn:claudecode", "B", "https://example.com/b", "2026-10-31T09:21:22+00:00", "要約"),
    ]


def test_save_skips_urls_already_stored_by_an_earlier_run(tmp_path):
    path = tmp_path / "news.db"
    with Database(path) as db:
        db.save([make_article("https://example.com/a")])

    # 翌週の実行を想定: 別の Database インスタンスで、同じ記事 + 新しい記事を保存する
    with Database(path) as db:
        added = db.save(
            [
                make_article("https://example.com/a"),
                make_article("https://example.com/c"),
            ]
        )

    assert added == 1
    assert [row[2] for row in read_rows(path)] == [
        "https://example.com/a",
        "https://example.com/c",
    ]


def test_save_skips_duplicate_urls_within_one_batch(tmp_path):
    path = tmp_path / "news.db"
    with Database(path) as db:
        added = db.save(
            [
                make_article("https://example.com/a"),
                make_article("https://example.com/a"),
            ]
        )

    assert added == 1
    assert len(read_rows(path)) == 1


def test_database_creates_missing_parent_directories(tmp_path):
    path = tmp_path / "data" / "nested" / "news.db"

    with Database(path) as db:
        added = db.save([make_article("https://example.com/a")])

    assert added == 1
    assert len(read_rows(path)) == 1


def test_average_length_returns_mean_summary_length(tmp_path):
    with Database(tmp_path / "news.db") as db:
        db.save(
            [
                make_article("https://example.com/a", summary="あいう"),
                make_article("https://example.com/b", summary="あいうえ"),
            ]
        )

        assert db.average_length() == 3.5


def test_average_length_returns_zero_when_no_articles(tmp_path):
    with Database(tmp_path / "news.db") as db:
        assert db.average_length() == 0.0


def test_count_articles_counts_title_or_summary_matches(tmp_path):
    with Database(tmp_path / "news.db") as db:
        db.save(
            [
                make_article("https://example.com/a", title="Claude Code 入門", summary="x"),
                make_article("https://example.com/b", title="other", summary="Claude の話"),
                make_article("https://example.com/c", title="other", summary="x"),
            ]
        )

        assert db.count_articles("Claude") == 2


def test_count_articles_returns_zero_when_no_match(tmp_path):
    with Database(tmp_path / "news.db") as db:
        db.save([make_article("https://example.com/a")])

        assert db.count_articles("存在しない") == 0


def test_count_articles_treats_wildcards_literally(tmp_path):
    with Database(tmp_path / "news.db") as db:
        db.save(
            [
                make_article("https://example.com/a", title="100% 達成"),
                make_article("https://example.com/b", title="abc"),
            ]
        )

        assert db.count_articles("%") == 1
        assert db.count_articles("_") == 0
