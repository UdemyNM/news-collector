# ニュース検索 MCP サーバー Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** news-collector がためた記事を Claude から検索できるよう、`search_news` と `get_article` の 2 ツールを持つ MCP サーバーを `mcp_server/server.py` に作る。

**Architecture:** 検索の中身は DB パスを受け取る純粋な関数（`search_articles` / `fetch_article`）に分け、MCP ツールはそれを呼ぶ薄い包みにする。サーバーは `create_server(db_path)` で作り、モジュール末尾の `mcp` が `config.toml` の DB を指す。DB は呼び出しのたびに読み取り専用で開く。

**Tech Stack:** Python 3.11+, SQLite（標準 `sqlite3`）, 公式 SDK `mcp[cli]` v2（`from mcp.server import MCPServer`。古い `FastMCP` は使わない）, pytest（非同期は anyio プラグイン）

**Spec:** この会話で合意した設計（設計書ファイルは作らない）。要点は下の Global Constraints に転記した。

## Global Constraints

- ツールは `search_news(keyword, since, until, source)`（全部省略可）と `get_article(id)` の 2 つだけ。
- `search_news` の結果は **最大 10 件固定**、`published_at` の新しい順。件数の引数は作らない。10 件を超えた分の件数は伝えない。
- 一覧の各項目は `id`・`title`・`source`・`published_at`・`url` の 5 つ。**`summary` は載せない。** 該当 0 件は空リスト。
- `keyword` は `title` と `summary` の部分一致。`source` は前方一致（`zenn` で `zenn:claudecode` に当たる。大文字小文字は区別しない）。
- `since` / `until` は `YYYY-MM-DD`。**日本時間（+09:00）の日付**として、`since` はその日の 0 時から、`until` はその日の終わりまで（含む）。`until` を省略すると今日（日本時間）まで。
- DB の `published_at` は UTC の ISO 文字列（`2026-10-31T09:21:22+00:00`）。比較する境界も同じ形式の UTC 文字列にして文字列比較する。
- `get_article(id)` は `id`・`source`・`title`・`url`・`published_at`・`summary` を返す。存在しない id は `ToolError`。
- DB は **読み取り専用**（`mode=ro`）で開く。サーバーから記事を書き換えない・DB を新規作成しない。
- DB の場所は `config.toml` の `[database] path`。既存の `news_collector.config.load_config` を再利用する。
- 起動は stdio（`mcp.run()` を `if __name__ == "__main__":` の中に置く）。標準出力に `print` しない。
- 変更するのは `mcp_server/server.py`（新規）、`pyproject.toml`（依存と pytest 設定）、テスト、`CLAUDE.md` のフォルダ構成だけ。`src/news_collector/` 本体は変えない。`settings.json`・`.mcp.json`・hook は触らない。登録コマンドは案内するだけで実行しない。
- コミットメッセージは日本語で簡潔に。末尾に `Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>`。main には直接 push しない。

## Review Focus

どのタスクのテストにも入れる「設計が黙っている入力」。各行のテストは、担当タスクの中に書いてある。

1. `keyword=""`（空文字）や `source=""`: 「省略」と同じ扱いにし、全件対象にする（Task 1）
2. `keyword="100%"` や `"a_b"`: `%` `_` を記号ではなく文字そのものとして探す（Task 1）
3. 日付が `"先週"` や `"2026-13-40"`: 例外で落とさず、分かるメッセージの `ToolError`（Task 1 で `ValueError`、Task 2 で `ToolError` に変換）
4. `since` が `until` より後: 同じく分かるメッセージのエラー（Task 1 / 2）
5. DB ファイルがまだない（`news-collector` 未実行）: 空の DB を作らず、「先に news-collector を実行する」と分かる `ToolError`（Task 2）
6. `published_at` が NULL の記事: 日付で絞るときは除外、絞らないときは一覧の最後に出す（Task 1）

---

### Task 1: 検索ロジックと依存の追加

**Files:**
- Modify: `pyproject.toml`（`dependencies` は変えない。`[project.optional-dependencies]` に `mcp = ["mcp[cli]"]` を足し、`dev` を `["pytest", "mcp[cli]"]` にする。`[tool.pytest.ini_options]` に `pythonpath = ["."]` を足す）
- Create: `mcp_server/server.py`（この Task では検索関数だけ）
- Test: `tests/test_mcp_search.py`

`dev` に `mcp[cli]` を入れるのは、CI（`.github/workflows/test.yml`）が `pip install -e ".[dev]"` だけを入れるため。

**Interfaces:**
- Produces:
  - `class ArticleSummary(TypedDict)`: `id: int, title: str, source: str, published_at: str | None, url: str`
  - `class ArticleDetail(TypedDict)`: `id: int, source: str, title: str, url: str, published_at: str | None, summary: str`
  - `def search_articles(db_path: Path, *, keyword: str | None, since: str | None, until: str | None, source: str | None, today: date) -> list[ArticleSummary]`
    - 日付が不正、または `since > until` のとき `ValueError`（メッセージは日本語で、悪い値を含める）
    - DB が開けないとき `sqlite3.OperationalError` をそのまま上げる
  - `def fetch_article(db_path: Path, article_id: int) -> ArticleDetail | None`（なければ `None`）
  - `def _connect_readonly(db_path: Path) -> sqlite3.Connection`（`Path.resolve().as_uri() + "?mode=ro"` を `uri=True` で開く。日本語パスでも動くように）

- [ ] **Step 0: ブランチを作る**

`git switch -c add-mcp-server`（今のブランチ `add-ci-tests` から分岐）。

- [ ] **Step 1: 依存を入れる**

`pyproject.toml` を上のとおり編集し、`.venv/Scripts/python.exe -m pip install -e ".[dev]"` を実行。`.venv/Scripts/python.exe -c "from mcp.server import MCPServer"` がエラーなく通ること。通らなければ（バージョンの食い違いなど）、ここで止めて報告する。

- [ ] **Step 2: 失敗するテストを書く（`tests/test_mcp_search.py`）**

テスト用 DB は、`Database` と `Article`（既存）で `tmp_path` に作るヘルパーを置く。テストの名前と、確かめる中身:

- `test_returns_newest_first_without_filters`: 3 件保存 → `published_at` の新しい順、キーは 5 つだけ（`summary` を含まない）
- `test_limits_to_10_results`: 12 件保存 → 10 件
- `test_keyword_matches_title_or_summary`: タイトルだけ・要約だけに入っている記事が両方当たる
- `test_keyword_treats_percent_and_underscore_literally`: `"100%"` は `"100% 完全"` に当たり `"1000"` には当たらない。`"a_b"` は `"axb"` に当たらない
- `test_empty_keyword_and_source_mean_no_filter`: `keyword=""`, `source=""` で全件
- `test_source_is_prefix_match_ignoring_case`: `source="Zenn"` が `zenn:claudecode` に当たり、`qiita:ClaudeCode` は除外
- `test_since_and_until_use_japan_time`: `published_at="2026-10-30T15:30:00+00:00"`（日本時間 10/31 0:30）は `since="2026-10-31"` に含まれ、`until="2026-10-30"` には含まれない。`published_at="2026-10-31T14:59:59+00:00"`（日本時間 10/31 23:59:59）は `until="2026-10-31"` に含まれ、`"2026-10-31T15:00:00+00:00"` は含まれない
- `test_until_defaults_to_today_in_japan`: `today=date(2026, 10, 31)` で、日本時間 11/1 0:00 以降の記事は出ない
- `test_null_published_at_excluded_when_dates_given_and_last_otherwise`
- `test_invalid_date_raises_value_error`: `since="先週"` と `"2026-13-40"` で `ValueError`、メッセージに悪い値が入る
- `test_since_after_until_raises_value_error`
- `test_fetch_article_returns_all_fields_or_none`: 存在する id は 6 項目すべて、存在しない id は `None`
- `test_connect_readonly_does_not_create_missing_db`: 存在しないパスで `sqlite3.OperationalError`、かつファイルが作られない

- [ ] **Step 3: 失敗を確かめる**

Run: `.venv/Scripts/python.exe -m pytest tests/test_mcp_search.py -v`
Expected: 収集時に `ModuleNotFoundError`（または `ImportError`）で FAIL。

- [ ] **Step 4: `mcp_server/server.py` に上の Interfaces を実装する**

SQL はプレースホルダ（`?`）で組み立て、`LIKE ... ESCAPE '\'` の前に `\` `%` `_` をエスケープする。並びは `ORDER BY published_at DESC, id DESC`（SQLite は DESC のとき NULL が最後になる）。日付は `date.fromisoformat`（`YYYY-MM-DD` 以外は `ValueError`）で読み、日本時間の境界を UTC の `%Y-%m-%dT%H:%M:%S+00:00` 文字列にして `published_at >= ?` と `published_at < ?`（翌日 0 時、排他）で比べる。

- [ ] **Step 5: 通ることを確かめる**

Run: `.venv/Scripts/python.exe -m pytest -v`
Expected: 既存のテストも含めて全部 PASS。

- [ ] **Step 6: コミット**

`git add pyproject.toml mcp_server/server.py tests/test_mcp_search.py` → 日本語のメッセージ（例: 「MCP サーバーの検索ロジックを追加」）。

---

### Task 2: MCP ツールとサーバーの組み立て

**Files:**
- Modify: `mcp_server/server.py`
- Test: `tests/test_mcp_server.py`

**Interfaces:**
- Consumes: Task 1 の `search_articles`, `fetch_article`, `ArticleSummary`, `ArticleDetail`
- Produces:
  - `def create_server(db_path: Path) -> MCPServer`: ツール `search_news` と `get_article` を登録して返す
  - モジュール変数 `mcp = create_server(load_config(<リポジトリ直下>/"config.toml").db_path)`（`mcp run` が見つける名前）
  - `search_news(keyword: str | None = None, since: str | None = None, until: str | None = None, source: str | None = None) -> list[ArticleSummary]`
  - `get_article(id: int) -> ArticleDetail`
  - 失敗はすべて `mcp.server.mcpserver.exceptions.ToolError`（Claude が読める日本語メッセージ）:
    - `ValueError` → そのメッセージ
    - `sqlite3.OperationalError` → 「記事 DB を開けません。先に `news-collector` を実行してください」
    - 存在しない id → 「id=〇 の記事は見つかりません」

docstring は Claude がツールを選ぶ手がかりになるので日本語で書く。`since`/`until` が `YYYY-MM-DD` の日本時間で、「先週」などは呼ぶ側が日付に直して渡すこと、結果は新しい順で最大 10 件であることを `search_news` の docstring に書く。`id` は `search_news` の結果にあるものを渡す、と `get_article` の docstring に書く。

- [ ] **Step 1: 失敗するテストを書く（`tests/test_mcp_server.py`）**

公式のテスト方法（`Client(server, raise_exceptions=True)`、`anyio_backend` フィクスチャ、`@pytest.mark.anyio`）を使う。`tmp_path` に DB を作り `create_server(db_path)` に渡す。

- `test_lists_two_tools`: `client.list_tools()` の名前が `search_news` と `get_article`、`search_news` の引数がすべて必須ではない
- `test_search_news_returns_structured_results`: `call_tool("search_news", {"keyword": "Claude Code", "source": "zenn"})` が `is_error is False`、`structured_content["result"]` の各項目のキーが 5 つだけで `summary` がない
- `test_search_news_without_arguments_returns_recent`: 引数なしで呼べて、新しい順
- `test_search_news_invalid_date_is_tool_error`: `since="先週"` で `is_error is True`、`content[0].text` に `先週` が入る。`since` が `until` より後でも同様（Review Focus 3, 4）
- `test_get_article_returns_all_fields`: 保存した記事の id で 6 項目すべて、`summary` を含む
- `test_get_article_unknown_id_is_tool_error`: `is_error is True`、テキストに `見つかりません`
- `test_missing_db_is_tool_error_and_not_created`: 存在しない DB パスで `search_news` → `is_error is True`、テキストに `news-collector`、ファイルが作られていない（Review Focus 5）

- [ ] **Step 2: 失敗を確かめる**

Run: `.venv/Scripts/python.exe -m pytest tests/test_mcp_server.py -v`
Expected: `ImportError`（`create_server` がない）で FAIL。

- [ ] **Step 3: `create_server` とモジュール末尾の `mcp`、`if __name__ == "__main__": mcp.run()` を実装する**

`search_news` の `today` は `datetime.now(timezone(timedelta(hours=9))).date()`。`mcp` を作る時点で DB は開かない（開くのは呼び出しのたび）。`print` は使わない。

- [ ] **Step 4: 全部通ることを確かめる**

Run: `.venv/Scripts/python.exe -m pytest -v`
Expected: 全部 PASS。

- [ ] **Step 5: コミット**

`git add mcp_server/server.py tests/test_mcp_server.py` → 日本語のメッセージ（例: 「search_news と get_article の MCP ツールを追加」）。

---

### Task 3: 実データでの動作確認とフォルダ構成の更新

**Files:**
- Modify: `CLAUDE.md`（「フォルダ構成」の図に `mcp_server/server.py   記事を検索する MCP サーバー（stdio）` を足す。図のほかは変えない）
- 一時ファイル: `.scratchpad/smoke.py`（確認が終わったら削除する）

- [ ] **Step 1: 実際の `data/news.db` に対してサーバーを呼ぶ**

`.scratchpad/smoke.py` で `from mcp_server.server import mcp` を `Client(mcp)` に渡し、`search_news`（引数なし）と `search_news(source="zenn", keyword="Claude Code")`、取れた最初の id での `get_article` を呼んで結果を表示する。Run: `PYTHONPATH=. .venv/Scripts/python.exe .scratchpad/smoke.py`（Git Bash の書き方）。
Expected: 3 つとも `is_error=False`。件数は 10 以下で、`summary` は一覧になく `get_article` にはある。`since="2026-10-19", until="2026-10-25"`（先週）の Zenn は、データが 10/30 以降しかないので **0 件になるのが正しい**。

- [ ] **Step 2: stdio で起動できることを確かめる**

Run: `uv run mcp dev mcp_server/server.py` は Inspector（ブラウザ）が必要なので使わない。代わりに `.venv/Scripts/python.exe mcp_server/server.py < NUL` が、標準出力に何も出さずに終了することを確かめる。

- [ ] **Step 3: 一時ファイルを消し、`CLAUDE.md` を更新する**

`.scratchpad/` を空にする（`ls .scratchpad` で何もないこと）。

- [ ] **Step 4: 全部の確認**

Run: `.venv/Scripts/python.exe -m pytest -v`
Expected: 全部 PASS。結果は superpowers:verification-before-completion に従って、実際の出力を見てから報告する。

- [ ] **Step 5: コミット**

`git add CLAUDE.md` → 日本語のメッセージ（例: 「フォルダ構成に mcp_server を追記」）。PR は頼まれたときだけ作る。

---

## 利用者向けの案内（実行はしない）

Claude Code に登録するコマンドは、完了報告で次の形を案内する。`<絶対パス>` はリポジトリの場所に置き換える。

```
claude mcp add news -- <絶対パス>\.venv\Scripts\python.exe <絶対パス>\mcp_server\server.py
```

`.venv` の Python を直接指定するので、`uv` は要らない。登録後は Claude Code で `/mcp` を開いて接続を確かめる。

## Self-Review

- **Spec coverage:** 2 ツール・最大 10 件・summary なし・件数を伝えない（Global Constraints と Task 1 の 2 テスト）、日本時間の日付と `until` 省略（Task 1）、前方一致の `source`（Task 1）、読み取り専用（Task 1 の `_connect_readonly` と Task 2 の「作られない」テスト）、`config.toml` 再利用（Task 2 のモジュール変数 `mcp`）、stdio（Task 2 Step 3 と Task 3 Step 2）、最新 SDK（`MCPServer`、`ToolError`、`Client(server)` でのテスト）、依存の追加と CI（Task 1）。抜けはない。
- **型の整合:** `search_articles` / `fetch_article` / `ArticleSummary` / `ArticleDetail` は Task 1 で定義し、Task 2 が同じ名前で使う。
- **Review Focus:** 6 項目とも、担当タスクのテストに入れた。
- **注意:** `mcp` の正確なバージョンと、`ToolError` の import 先（`mcp.server.mcpserver.exceptions`）は、公式ドキュメントの記述どおり。Task 1 Step 1 の import 確認で食い違いがあれば、そこで止まる。
