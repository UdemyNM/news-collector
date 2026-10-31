from datetime import UTC, datetime

import feedparser
import httpx

from news_collector.config import SourceConfig
from news_collector.models import Article

_SUMMARY_LIMIT = 300


class FetchError(Exception):
    """取得はできたが、期待した形式のデータではなかった。"""


def fetch_articles(client: httpx.Client, source: SourceConfig) -> list[Article]:
    if source.type == "zenn":
        return _fetch_feed(
            client,
            url=f"https://zenn.dev/topics/{source.target}/feed",
            label=source.label,
        )
    if source.type == "qiita":
        return _fetch_feed(
            client,
            url=f"https://qiita.com/tags/{source.target}/feed",
            label=source.label,
        )
    if source.type == "github_releases":
        return _fetch_github_releases(client, source.target, label=source.label)
    raise ValueError(f"未知の type です: {source.type!r}")


def _fetch_feed(client: httpx.Client, url: str, label: str) -> list[Article]:
    response = client.get(url)
    response.raise_for_status()

    feed = feedparser.parse(response.content)
    # フィードと認識できた場合だけ version（"rss20" など）が入る。HTML や空の応答では空
    if not feed.get("version"):
        raise FetchError(f"フィードとして解釈できません: {url}")

    return [
        Article(
            source=label,
            title=entry.title,
            url=entry.link,
            published_at=_feed_time_to_iso(entry.get("published_parsed")),
            summary=entry.get("summary", "")[:_SUMMARY_LIMIT],
        )
        for entry in feed.entries
    ]


def _fetch_github_releases(client: httpx.Client, repo: str, label: str) -> list[Article]:
    url = f"https://api.github.com/repos/{repo}/releases"
    response = client.get(url)
    response.raise_for_status()

    releases = response.json()
    if not isinstance(releases, list):
        raise FetchError(f"リリース一覧ではない応答です: {url}")

    return [
        Article(
            source=label,
            title=release["name"] or release["tag_name"],
            url=release["html_url"],
            published_at=_github_time_to_iso(release.get("published_at")),
            summary=(release.get("body") or "")[:_SUMMARY_LIMIT],
        )
        for release in releases
    ]


def _feed_time_to_iso(parsed) -> str | None:
    # feedparser は日時を UTC の struct_time にそろえて返す
    if parsed is None:
        return None
    return datetime(*parsed[:6], tzinfo=UTC).isoformat()


def _github_time_to_iso(value: str | None) -> str | None:
    if value is None:
        return None
    return datetime.fromisoformat(value).astimezone(UTC).isoformat()
