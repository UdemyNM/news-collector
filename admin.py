"""ためた記事の管理画面（Tkinter の GUI）。

出どころごとの記事件数と、記事一覧（10 件）をウィンドウに表示する。
    python admin.py                         全出どころの新しい記事 10 件
    python admin.py --source qiita:ClaudeCode   その出どころを選んだ状態で開く

画面上のプルダウンでも出どころを切り替えられる。
一覧の行をダブルクリックすると、記事の URL をブラウザで開く。
"""

import argparse
import re
import sqlite3
import sys
import webbrowser
from dataclasses import dataclass, replace
from pathlib import Path

from news_collector.config import ConfigError, load_config
from news_collector.db import Database
from news_collector.models import Article

CONFIG_PATH = Path(__file__).resolve().parent / "config.toml"
LIST_LIMIT = 10
ALL_SOURCES = "すべて"
_CONTROL_CHARS = re.compile(r"[\x00-\x1f\x7f-\x9f]")


class AdminError(Exception):
    """画面に出す前の失敗（設定・DB・出どころ指定の誤り）。"""


@dataclass(frozen=True)
class AdminView:
    counts: dict[str, int]
    articles: list[Article]


def _clean(text: str) -> str:
    """外部フィード由来の文字列から制御文字（ANSI エスケープを含む）を除く。"""
    return _CONTROL_CHARS.sub("", text)


def load_view(source=None, config_path=CONFIG_PATH) -> AdminView:
    """DB から画面に出す内容（出どころ別件数と一覧）を読む。"""
    try:
        config = load_config(config_path)
    except ConfigError as e:
        raise AdminError(str(e)) from e

    # 閲覧専用なので、DB がないときに Database() で空の DB を作ってしまわない
    if not Path(config.db_path).exists():
        raise AdminError("DB がありません。先に news-collector を実行してください")

    try:
        with Database(config.db_path) as db:
            counts = db.count_by_source()
            if source is not None and source not in counts:
                known = ", ".join(counts) or "なし"
                raise AdminError(
                    f"出どころ {source!r} の記事はありません（あるもの: {known}）"
                )
            articles = [
                replace(
                    a, title=_clean(a.title), url=_clean(a.url), source=_clean(a.source)
                )
                for a in db.list_articles(source=source, limit=LIST_LIMIT)
            ]
    except sqlite3.Error as e:
        raise AdminError(f"DB を読めません: {e}") from e
    return AdminView(counts=counts, articles=articles)


def show_window(view: AdminView, source, reload) -> None:
    """Tkinter で管理画面を開く。ウィンドウを閉じるまで戻らない。

    reload(source) は出どころを切り替えたときに呼ばれ、新しい AdminView を返す。
    """
    import tkinter as tk
    from tkinter import messagebox, ttk

    try:
        root = tk.Tk()
    except tk.TclError as e:
        # ディスプレイがない環境（SSH・ヘッドレス CI など）
        raise AdminError(f"画面を開けません: {e}") from e
    root.title("news-collector 管理画面")
    root.geometry("900x520")

    # --- 出どころごとの件数 ---
    counts_frame = ttk.LabelFrame(root, text="出どころごとの件数")
    counts_frame.pack(fill="x", padx=8, pady=(8, 4))
    counts_tree = ttk.Treeview(
        counts_frame, columns=("source", "count"), show="headings", height=4
    )
    counts_tree.heading("source", text="出どころ")
    counts_tree.heading("count", text="件数")
    counts_tree.column("source", width=400)
    counts_tree.column("count", width=80, anchor="e")
    counts_tree.pack(fill="x", padx=4, pady=4)

    # --- 一覧の絞り込み ---
    select_frame = ttk.Frame(root)
    select_frame.pack(fill="x", padx=8, pady=4)
    ttk.Label(select_frame, text="出どころ:").pack(side="left")
    selected = tk.StringVar(value=source or ALL_SOURCES)
    combo = ttk.Combobox(
        select_frame,
        textvariable=selected,
        state="readonly",
        values=[ALL_SOURCES, *view.counts],
        width=40,
    )
    combo.pack(side="left", padx=4)

    # --- 記事一覧 ---
    list_frame = ttk.LabelFrame(
        root, text=f"記事一覧（新しい順 最大 {LIST_LIMIT} 件・ダブルクリックで開く）"
    )
    list_frame.pack(fill="both", expand=True, padx=8, pady=(4, 8))
    articles_tree = ttk.Treeview(
        list_frame, columns=("date", "source", "title", "url"), show="headings"
    )
    for name, text, width in [
        ("date", "日付", 90),
        ("source", "出どころ", 140),
        ("title", "タイトル", 340),
        ("url", "URL", 300),
    ]:
        articles_tree.heading(name, text=text)
        articles_tree.column(name, width=width)
    articles_tree.pack(fill="both", expand=True, padx=4, pady=4)

    def render(current: AdminView) -> None:
        counts_tree.delete(*counts_tree.get_children())
        for src, count in current.counts.items():
            counts_tree.insert("", "end", values=(src, f"{count} 件"))
        articles_tree.delete(*articles_tree.get_children())
        for a in current.articles:
            date = (a.published_at or "日付なし")[:10]
            articles_tree.insert("", "end", values=(date, a.source, a.title, a.url))
        if not current.counts:
            articles_tree.insert("", "end", values=("", "", "記事がありません", ""))

    def on_select(_event=None) -> None:
        choice = selected.get()
        try:
            render(reload(None if choice == ALL_SOURCES else choice))
        except AdminError as e:
            messagebox.showerror("エラー", str(e))

    def on_open(_event=None) -> None:
        focus = articles_tree.focus()
        if not focus:
            return
        url = articles_tree.item(focus, "values")[3]
        if url.startswith(("http://", "https://")):
            webbrowser.open(url)

    combo.bind("<<ComboboxSelected>>", on_select)
    articles_tree.bind("<Double-1>", on_open)
    render(view)
    root.mainloop()


def main(argv=None, config_path=CONFIG_PATH, show=show_window) -> int:
    parser = argparse.ArgumentParser(description="ためた記事を出どころごとに見る")
    parser.add_argument(
        "--source", help="最初に選んでおく出どころ（例: zenn:claudecode）。省略すると全部"
    )
    args = parser.parse_args(argv)

    try:
        view = load_view(args.source, config_path)
    except AdminError as e:
        print(f"エラー: {e}", file=sys.stderr)
        return 1

    try:
        show(view, args.source, lambda source: load_view(source, config_path))
    except AdminError as e:
        print(f"エラー: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
