"""ためた記事の管理画面（コマンドライン）。

出どころごとの記事件数と、記事一覧（10 件）を表示する。
    python admin.py                         全出どころの新しい記事 10 件
    python admin.py --source qiita:ClaudeCode   その出どころだけ 10 件
"""

import argparse
import re
import sys
from pathlib import Path

from news_collector.config import ConfigError, load_config
from news_collector.db import Database

CONFIG_PATH = Path(__file__).resolve().parent / "config.toml"
LIST_LIMIT = 10
_CONTROL_CHARS = re.compile(r"[\x00-\x1f\x7f-\x9f]")


def _clean(text: str) -> str:
    """外部フィード由来の文字列から制御文字（ANSI エスケープを含む）を除く。"""
    return _CONTROL_CHARS.sub("", text)


def main(argv=None, config_path=CONFIG_PATH) -> int:
    parser = argparse.ArgumentParser(description="ためた記事を出どころごとに見る")
    parser.add_argument(
        "--source", help="一覧に出す出どころ（例: zenn:claudecode）。省略すると全部"
    )
    args = parser.parse_args(argv)

    try:
        config = load_config(config_path)
    except ConfigError as e:
        print(f"エラー: {e}", file=sys.stderr)
        return 1

    # 閲覧専用なので、DB がないときに Database() で空の DB を作ってしまわない
    if not Path(config.db_path).exists():
        print(
            "エラー: DB がありません。先に news-collector を実行してください",
            file=sys.stderr,
        )
        return 1

    with Database(config.db_path) as db:
        counts = db.count_by_source()
        if args.source is not None and args.source not in counts:
            known = ", ".join(counts) or "なし"
            print(
                f"エラー: 出どころ {args.source!r} の記事はありません（あるもの: {known}）",
                file=sys.stderr,
            )
            return 1

        print("== 出どころごとの件数 ==")
        if not counts:
            print("記事がありません")
            return 0
        for source, count in counts.items():
            mark = "*" if source == args.source else " "
            print(f"{mark} {source}: {count} 件")

        label = args.source or "すべて"
        print(f"\n== 記事一覧（{label}、新しい順 最大 {LIST_LIMIT} 件）==")
        for article in db.list_articles(source=args.source, limit=LIST_LIMIT):
            date = (article.published_at or "日付なし")[:10]
            title = _clean(article.title)
            url = _clean(article.url)
            print(f"{date}  [{article.source}] {title}\n           {url}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
