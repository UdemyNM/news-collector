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


def test_shows_counts_and_all_articles_by_default(tmp_path, capsys):
    config = setup_env(tmp_path)

    assert admin.main([], config_path=config) == 0

    out = capsys.readouterr().out
    assert "zenn:claudecode" in out and "2 件" in out
    assert "qiita:ClaudeCode" in out and "1 件" in out
    assert "Z0" in out and "Q0" in out


def test_source_option_switches_the_list(tmp_path, capsys):
    config = setup_env(tmp_path)

    assert admin.main(["--source", "qiita:ClaudeCode"], config_path=config) == 0

    out = capsys.readouterr().out
    assert "Q0" in out
    assert "Z0" not in out
    assert "zenn:claudecode" in out  # 件数は全出どころ分を表示する


def test_list_is_limited_to_10(tmp_path, capsys):
    config = setup_env(tmp_path, zenn=15, qiita=0)

    admin.main([], config_path=config)

    out = capsys.readouterr().out
    assert out.count("https://example.com/z") == 10


def test_unknown_source_returns_error(tmp_path, capsys):
    config = setup_env(tmp_path)

    assert admin.main(["--source", "nothing"], config_path=config) == 1
    assert "nothing" in capsys.readouterr().err


def test_empty_db_shows_zero_articles(tmp_path, capsys):
    config = setup_env(tmp_path, zenn=0, qiita=0)

    assert admin.main([], config_path=config) == 0
    assert "記事がありません" in capsys.readouterr().out


def test_missing_db_returns_error_without_creating_it(tmp_path, capsys):
    config = tmp_path / "config.toml"
    config.write_text(CONFIG, encoding="utf-8")

    assert admin.main([], config_path=config) == 1
    assert "DB がありません" in capsys.readouterr().err
    assert not (tmp_path / "news.db").exists()


def test_control_characters_are_stripped_from_output(tmp_path, capsys):
    config = tmp_path / "config.toml"
    config.write_text(CONFIG, encoding="utf-8")
    with Database(tmp_path / "news.db") as db:
        db.save([Article("zenn:claudecode", "ev\x1b[31mil", "https://example.com/\x07a", None, "s")])

    admin.main([], config_path=config)

    out = capsys.readouterr().out
    assert "\x1b" not in out and "\x07" not in out
    assert "ev[31mil" in out
