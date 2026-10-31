import json
import sqlite3

import httpx

from news_collector.cli import main
from sample_data import QIITA_ATOM, ZENN_RSS, github_release

CONFIG_TOML = """
[database]
path = "news.db"

[[sources]]
type = "zenn"
tag = "claudecode"

[[sources]]
type = "qiita"
tag = "ClaudeCode"

[[sources]]
type = "github_releases"
repo = "anthropics/claude-code"
"""


def make_client(routes):
    """routes: {ホスト名: レスポンスを返す関数 / 例外}。ホストごとに応答を切り替える。"""

    def handler(request):
        outcome = routes[request.url.host]
        if isinstance(outcome, Exception):
            raise outcome
        return outcome

    return httpx.Client(transport=httpx.MockTransport(handler))


def ok_routes():
    return {
        "zenn.dev": httpx.Response(200, text=ZENN_RSS),
        "qiita.com": httpx.Response(200, text=QIITA_ATOM),
        "api.github.com": httpx.Response(200, json=[github_release()]),
    }


def setup_config(tmp_path, text=CONFIG_TOML):
    path = tmp_path / "config.toml"
    path.write_text(text, encoding="utf-8")
    return path


def stored_sources(tmp_path):
    conn = sqlite3.connect(tmp_path / "news.db")
    try:
        rows = conn.execute("SELECT source, COUNT(*) FROM articles GROUP BY source").fetchall()
    finally:
        conn.close()
    return dict(rows)


def test_all_sources_succeed_stores_articles_and_exits_0(tmp_path):
    config = setup_config(tmp_path)

    code = main(["--config", str(config)], client=make_client(ok_routes()))

    assert code == 0
    assert stored_sources(tmp_path) == {
        "zenn:claudecode": 2,
        "qiita:ClaudeCode": 1,
        "github:anthropics/claude-code": 1,
    }


def test_one_http_error_does_not_stop_the_others_and_exits_0(tmp_path, capsys):
    config = setup_config(tmp_path)
    routes = ok_routes()
    routes["zenn.dev"] = httpx.Response(500, text="boom")

    code = main(["--config", str(config)], client=make_client(routes))

    assert code == 0
    assert stored_sources(tmp_path) == {
        "qiita:ClaudeCode": 1,
        "github:anthropics/claude-code": 1,
    }
    err = capsys.readouterr().err
    assert "zenn:claudecode" in err  # 失敗したソースが分かる
    assert "qiita:ClaudeCode" not in err  # 成功したソースは失敗として出さない


def test_a_network_exception_in_the_first_source_does_not_stop_the_rest(tmp_path):
    config = setup_config(tmp_path)
    routes = ok_routes()
    routes["zenn.dev"] = httpx.ConnectError("接続できません")

    code = main(["--config", str(config)], client=make_client(routes))

    assert code == 0
    assert set(stored_sources(tmp_path)) == {
        "qiita:ClaudeCode",
        "github:anthropics/claude-code",
    }


def test_an_unparseable_response_in_the_middle_does_not_stop_the_rest(tmp_path):
    config = setup_config(tmp_path)
    routes = ok_routes()
    routes["qiita.com"] = httpx.Response(200, text="<html><body>メンテナンス中</body></html>")
    routes["api.github.com"] = httpx.Response(200, text=json.dumps({"message": "?"}))

    code = main(["--config", str(config)], client=make_client(routes))

    assert code == 0
    assert stored_sources(tmp_path) == {"zenn:claudecode": 2}


def test_all_sources_failing_exits_1(tmp_path):
    config = setup_config(tmp_path)
    routes = {
        "zenn.dev": httpx.Response(500),
        "qiita.com": httpx.ConnectError("接続できません"),
        "api.github.com": httpx.Response(403, json={"message": "rate limit"}),
    }

    code = main(["--config", str(config)], client=make_client(routes))

    assert code == 1
    assert stored_sources(tmp_path) == {}


def test_a_source_that_succeeds_with_zero_articles_counts_as_success(tmp_path):
    config = setup_config(
        tmp_path,
        '[database]\npath = "news.db"\n[[sources]]\ntype = "github_releases"\nrepo = "a/b"\n',
    )
    routes = {"api.github.com": httpx.Response(200, json=[])}

    code = main(["--config", str(config)], client=make_client(routes))

    assert code == 0


def test_running_twice_does_not_duplicate_articles(tmp_path):
    config = setup_config(tmp_path)

    main(["--config", str(config)], client=make_client(ok_routes()))
    code = main(["--config", str(config)], client=make_client(ok_routes()))

    assert code == 0
    assert stored_sources(tmp_path) == {
        "zenn:claudecode": 2,
        "qiita:ClaudeCode": 1,
        "github:anthropics/claude-code": 1,
    }


def test_config_defaults_to_config_toml_in_the_current_directory(tmp_path, monkeypatch):
    setup_config(tmp_path)
    monkeypatch.chdir(tmp_path)

    code = main([], client=make_client(ok_routes()))

    assert code == 0
    assert len(stored_sources(tmp_path)) == 3


def test_invalid_config_exits_2_without_fetching(tmp_path, capsys):
    config = setup_config(tmp_path, "[database]\npath = 'news.db'\n")  # sources がない
    requested = []

    def handler(request):
        requested.append(str(request.url))
        return httpx.Response(200)

    client = httpx.Client(transport=httpx.MockTransport(handler))

    code = main(["--config", str(config)], client=client)

    assert code == 2
    assert requested == []
    assert "sources" in capsys.readouterr().err
