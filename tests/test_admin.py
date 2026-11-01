import pytest

import admin
from news_collector.db import Database
from news_collector.models import Article

CONFIG = """
[database]
path = "news.db"

[[sources]]
type = "zenn"
tag = "claudecode"
"""


def setup_env(tmp_path, zenn=2, qiita=1):
    (tmp_path / "config.toml").write_text(CONFIG, encoding="utf-8")
    articles = [
        Article("zenn:claudecode", f"Z{i}", f"https://example.com/z{i}", "2026-10-31T00:00:00+00:00", "s")
        for i in range(zenn)
    ] + [
        Article("qiita:ClaudeCode", f"Q{i}", f"https://example.com/q{i}", "2026-10-30T00:00:00+00:00", "s")
        for i in range(qiita)
    ]
    with Database(tmp_path / "news.db") as db:
        db.save(articles)
    return tmp_path / "config.toml"


def test_load_view_returns_counts_and_all_articles_by_default(tmp_path):
    config = setup_env(tmp_path)

    view = admin.load_view(None, config_path=config)

    assert view.counts == {"zenn:claudecode": 2, "qiita:ClaudeCode": 1}
    titles = {a.title for a in view.articles}
    assert {"Z0", "Q0"} <= titles


def test_load_view_source_switches_the_list_but_not_the_counts(tmp_path):
    config = setup_env(tmp_path)

    view = admin.load_view("qiita:ClaudeCode", config_path=config)

    assert {a.title for a in view.articles} == {"Q0"}
    assert "zenn:claudecode" in view.counts  # 件数は全出どころ分


def test_load_view_list_is_limited_to_10(tmp_path):
    config = setup_env(tmp_path, zenn=15, qiita=0)

    view = admin.load_view(None, config_path=config)

    assert len(view.articles) == 10


def test_load_view_unknown_source_raises(tmp_path):
    config = setup_env(tmp_path)

    with pytest.raises(admin.AdminError, match="nothing"):
        admin.load_view("nothing", config_path=config)


def test_load_view_empty_db_has_no_articles(tmp_path):
    config = setup_env(tmp_path, zenn=0, qiita=0)

    view = admin.load_view(None, config_path=config)

    assert view.counts == {} and view.articles == []


def test_load_view_missing_db_raises_without_creating_it(tmp_path):
    config = tmp_path / "config.toml"
    config.write_text(CONFIG, encoding="utf-8")

    with pytest.raises(admin.AdminError, match="DB がありません"):
        admin.load_view(None, config_path=config)
    assert not (tmp_path / "news.db").exists()


def test_load_view_strips_control_characters(tmp_path):
    config = tmp_path / "config.toml"
    config.write_text(CONFIG, encoding="utf-8")
    with Database(tmp_path / "news.db") as db:
        db.save([Article("zenn:claudecode", "ev\x1b[31mil", "https://example.com/\x07a", None, "s")])

    view = admin.load_view(None, config_path=config)

    article = view.articles[0]
    assert "\x1b" not in article.title and "\x07" not in article.url
    assert article.title == "ev[31mil"


def test_load_view_broken_db_raises_admin_error(tmp_path):
    config = tmp_path / "config.toml"
    config.write_text(CONFIG, encoding="utf-8")
    (tmp_path / "news.db").write_text("これは SQLite ではない" * 100, encoding="utf-8")

    with pytest.raises(admin.AdminError, match="DB を読めません"):
        admin.load_view(None, config_path=config)


def test_main_broken_db_returns_error(tmp_path, capsys):
    config = tmp_path / "config.toml"
    config.write_text(CONFIG, encoding="utf-8")
    (tmp_path / "news.db").write_text("これは SQLite ではない" * 100, encoding="utf-8")

    code = admin.main([], config_path=config, show=lambda *a: None)

    assert code == 1
    assert "DB を読めません" in capsys.readouterr().err


def test_main_window_failure_returns_error(tmp_path, capsys):
    config = setup_env(tmp_path)

    def show(*_):
        raise admin.AdminError("画面を開けません: no display")

    code = admin.main([], config_path=config, show=show)

    assert code == 1
    assert "画面を開けません" in capsys.readouterr().err


def test_show_window_without_display_raises_admin_error(monkeypatch):
    tk = pytest.importorskip("tkinter")

    def no_display(*_a, **_k):
        raise tk.TclError("no display name")

    monkeypatch.setattr(tk, "Tk", no_display)

    with pytest.raises(admin.AdminError, match="画面を開けません"):
        admin.show_window(admin.AdminView({}, []), None, lambda s: None)


def test_main_passes_view_and_source_to_show(tmp_path):
    config = setup_env(tmp_path)
    calls = []

    code = admin.main(
        ["--source", "qiita:ClaudeCode"],
        config_path=config,
        show=lambda view, source, reload: calls.append((view, source, reload)),
    )

    assert code == 0
    (view, source, reload), = calls
    assert source == "qiita:ClaudeCode"
    assert {a.title for a in view.articles} == {"Q0"}
    # 画面から出どころを切り替えるときに使う再読み込み関数
    assert {a.title for a in reload(None).articles} >= {"Z0", "Q0"}


def test_main_unknown_source_returns_error_and_skips_window(tmp_path, capsys):
    config = setup_env(tmp_path)
    calls = []

    code = admin.main(
        ["--source", "nothing"], config_path=config, show=lambda *a: calls.append(a)
    )

    assert code == 1
    assert "nothing" in capsys.readouterr().err
    assert calls == []


def test_main_missing_db_returns_error(tmp_path, capsys):
    config = tmp_path / "config.toml"
    config.write_text(CONFIG, encoding="utf-8")

    code = admin.main([], config_path=config, show=lambda *a: None)

    assert code == 1
    assert "DB がありません" in capsys.readouterr().err
    assert not (tmp_path / "news.db").exists()
