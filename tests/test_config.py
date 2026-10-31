import pytest

from news_collector.config import Config, ConfigError, SourceConfig, load_config


def write(tmp_path, text):
    path = tmp_path / "config.toml"
    path.write_text(text, encoding="utf-8")
    return path


def test_load_config_reads_database_and_all_three_source_types(tmp_path):
    path = write(
        tmp_path,
        """
[database]
path = "data/news.db"

[[sources]]
type = "zenn"
tag = "claudecode"

[[sources]]
type = "qiita"
tag = "ClaudeCode"

[[sources]]
type = "github_releases"
repo = "anthropics/claude-code"
""",
    )

    config = load_config(path)

    assert config == Config(
        db_path=tmp_path / "data" / "news.db",
        sources=[
            SourceConfig(type="zenn", target="claudecode"),
            SourceConfig(type="qiita", target="ClaudeCode"),
            SourceConfig(type="github_releases", target="anthropics/claude-code"),
        ],
    )


def test_relative_database_path_is_resolved_from_the_config_file_not_cwd(tmp_path, monkeypatch):
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    monkeypatch.chdir(elsewhere)
    path = write(
        tmp_path,
        """
[database]
path = "news.db"

[[sources]]
type = "zenn"
tag = "claudecode"
""",
    )

    assert load_config(path).db_path == tmp_path / "news.db"


@pytest.mark.parametrize(
    "body",
    [
        # 取得対象が 1 つもない
        '[database]\npath = "news.db"\n',
        # 未知の type
        '[database]\npath = "n.db"\n[[sources]]\ntype = "twitter"\ntag = "x"\n',
        # zenn に tag がない
        '[database]\npath = "n.db"\n[[sources]]\ntype = "zenn"\n',
        # qiita に tag がない（repo だけある）
        '[database]\npath = "n.db"\n[[sources]]\ntype = "qiita"\nrepo = "a/b"\n',
        # github_releases に repo がない
        '[database]\npath = "n.db"\n[[sources]]\ntype = "github_releases"\ntag = "x"\n',
        # database.path がない
        '[[sources]]\ntype = "zenn"\ntag = "claudecode"\n',
    ],
)
def test_invalid_config_raises_config_error(tmp_path, body):
    path = write(tmp_path, body)

    with pytest.raises(ConfigError):
        load_config(path)


def test_missing_config_file_raises_config_error(tmp_path):
    with pytest.raises(ConfigError):
        load_config(tmp_path / "nope.toml")


def test_malformed_toml_raises_config_error(tmp_path):
    path = write(tmp_path, "[database\npath = ")

    with pytest.raises(ConfigError):
        load_config(path)
