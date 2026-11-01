from dataclasses import dataclass


@dataclass(frozen=True)
class Article:
    source: str
    title: str
    url: str
    published_at: str | None
    summary: str


def average_summary_length(articles: list[Article]) -> float:
    """記事の summary の平均文字数を返す。"""
    return sum(len(a.summary) for a in articles) / len(articles)
