import argparse
import sys
from pathlib import Path

import httpx

from news_collector.config import ConfigError, load_config
from news_collector.db import Database
from news_collector.sources import fetch_articles


def main(argv=None, client: httpx.Client | None = None) -> int:
    """終了コード: 0 = 1 つ以上成功 / 1 = 全ソース失敗 / 2 = 設定エラー。"""
    parser = argparse.ArgumentParser(
        prog="news-collector",
        description="Zenn / Qiita / GitHub Releases のニュースを SQLite に集める",
    )
    parser.add_argument(
        "--config", type=Path, default=Path("config.toml"), help="設定ファイル (既定: ./config.toml)"
    )
    args = parser.parse_args(argv)

    try:
        config = load_config(args.config)
    except ConfigError as e:
        print(f"設定エラー: {e}", file=sys.stderr)
        return 2

    owns_client = client is None
    if owns_client:
        client = httpx.Client(
            timeout=15, follow_redirects=True, headers={"User-Agent": "news-collector/0.1"}
        )

    succeeded = 0
    try:
        with Database(config.db_path) as db:
            for source in config.sources:
                try:
                    articles = fetch_articles(client, source)
                    added = db.save(articles)
                except Exception as e:  # 1 つのソースの失敗で、残りを止めない
                    print(f"{source.label}: 失敗 ({type(e).__name__}: {e})", file=sys.stderr)
                    continue
                succeeded += 1
                print(f"{source.label}: {len(articles)}件取得、新規{added}件")
    finally:
        if owns_client:
            client.close()

    return 0 if succeeded else 1
