from dataclasses import dataclass


@dataclass(frozen=True)
class Article:
    source: str
    title: str
    url: str
    published_at: str | None
    summary: str
