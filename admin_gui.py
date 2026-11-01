"""ためた記事の管理画面（Tkinter の GUI）。

    python admin_gui.py

左に出どころごとの件数、右に選んだ出どころの記事一覧（新しい順 10 件）を出す。
データの読み取りは admin.py と同じ設定・DB を使う。
"""

from pathlib import Path

from admin import CONFIG_PATH, LIST_LIMIT, _clean
from news_collector.config import ConfigError, load_config
from news_collector.db import Database
from news_collector.models import Article

ALL_LABEL = "すべて"


class AdminError(Exception):
    """画面に出すエラー（設定の不備、DB なし、出どころなし）。"""


def load_view(
    config_path=CONFIG_PATH, source: str | None = None, limit: int = LIST_LIMIT
) -> tuple[dict[str, int], list[Article]]:
    """(出どころごとの件数, 記事一覧) を返す。source が None なら全出どころ。"""
    try:
        config = load_config(config_path)
    except ConfigError as e:
        raise AdminError(str(e)) from e

    # 閲覧専用なので、DB がないときに空の DB を作らない
    if not Path(config.db_path).exists():
        raise AdminError("DB がありません。先に news-collector を実行してください")

    with Database(config.db_path) as db:
        counts = db.count_by_source()
        if source is not None and source not in counts:
            known = ", ".join(counts) or "なし"
            raise AdminError(
                f"出どころ {source!r} の記事はありません（あるもの: {known}）"
            )
        return counts, db.list_articles(source=source, limit=limit)


def run_gui(config_path=CONFIG_PATH) -> None:
    import tkinter as tk
    from tkinter import messagebox, ttk

    root = tk.Tk()
    root.title("news-collector 管理画面")
    root.geometry("900x420")

    sources = ttk.Treeview(root, columns=("count",), height=10)
    sources.heading("#0", text="出どころ")
    sources.heading("count", text="件数")
    sources.column("#0", width=200)
    sources.column("count", width=60, anchor="e")
    sources.pack(side="left", fill="y", padx=8, pady=8)

    articles = ttk.Treeview(root, columns=("date", "source", "title"), show="headings")
    for col, text, width in (("date", "日付", 90), ("source", "出どころ", 150), ("title", "タイトル", 400)):
        articles.heading(col, text=text)
        articles.column(col, width=width)
    articles.pack(side="left", fill="both", expand=True, padx=(0, 8), pady=8)

    urls: dict[str, str] = {}  # 行 ID -> URL

    def show(source: str | None, refresh_sources: bool = False) -> None:
        try:
            counts, items = load_view(config_path, source)
        except AdminError as e:
            messagebox.showerror("エラー", str(e))
            return
        if refresh_sources:  # 選択イベントの中では作り直さない（再発火を避ける）
            sources.delete(*sources.get_children())
            sources.insert("", "end", iid=ALL_LABEL, text=ALL_LABEL, values=(sum(counts.values()),))
            for name, count in counts.items():
                sources.insert("", "end", iid=name, text=name, values=(count,))
            sources.selection_set(ALL_LABEL)
        articles.delete(*articles.get_children())
        urls.clear()
        for a in items:
            iid = articles.insert(
                "",
                "end",
                values=((a.published_at or "日付なし")[:10], a.source, _clean(a.title)),
            )
            urls[iid] = _clean(a.url)

    def on_select(_event) -> None:
        sel = sources.selection()
        if sel:
            show(None if sel[0] == ALL_LABEL else sel[0])

    def on_open(_event) -> None:
        sel = articles.selection()
        if sel:
            root.clipboard_clear()
            root.clipboard_append(urls[sel[0]])
            root.title(f"URL をコピーしました: {urls[sel[0]]}")

    sources.bind("<<TreeviewSelect>>", on_select)
    articles.bind("<Double-1>", on_open)

    show(None, refresh_sources=True)
    root.mainloop()


if __name__ == "__main__":
    run_gui()
