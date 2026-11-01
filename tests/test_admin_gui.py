import pytest

import admin_gui
from news_collector.db import Database
from tests.test_admin import CONFIG, setup_env


def test_load_view_returns_counts_and_all_articles(tmp_path):
    config = setup_env(tmp_path)

    counts, articles = admin_gui.load_view(config)

    assert counts == {"zenn:claudecode": 2, "qiita:ClaudeCode": 1}
    assert len(articles) == 3


def test_load_view_filters_by_source(tmp_path):
    config = setup_env(tmp_path)

    counts, articles = admin_gui.load_view(config, source="qiita:ClaudeCode")

    assert [a.title for a in articles] == ["Q0"]
    assert counts["zenn:claudecode"] == 2  # 件数は全出どころ分


def test_load_view_limits_to_10(tmp_path):
    config = setup_env(tmp_path, zenn=15, qiita=0)

    _, articles = admin_gui.load_view(config)

    assert len(articles) == 10


def test_load_view_without_db_raises(tmp_path):
    (tmp_path / "config.toml").write_text(CONFIG, encoding="utf-8")

    with pytest.raises(admin_gui.AdminError, match="DB がありません"):
        admin_gui.load_view(tmp_path / "config.toml")
    assert not (tmp_path / "news.db").exists()


def test_load_view_empty_db(tmp_path):
    (tmp_path / "config.toml").write_text(CONFIG, encoding="utf-8")
    Database(tmp_path / "news.db").close()

    assert admin_gui.load_view(tmp_path / "config.toml") == ({}, [])


def test_load_view_unknown_source_raises(tmp_path):
    config = setup_env(tmp_path)

    with pytest.raises(admin_gui.AdminError, match="nope"):
        admin_gui.load_view(config, source="nope")


def test_load_view_bad_config_raises(tmp_path):
    with pytest.raises(admin_gui.AdminError):
        admin_gui.load_view(tmp_path / "missing.toml")
