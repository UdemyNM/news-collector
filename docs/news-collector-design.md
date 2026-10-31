# news-collector 設計書

作成日: 2026-10-31

## 目的

技術ニュースを毎週月曜にまとめて読みたい個人のために、情報源から記事を集めて SQLite に貯める。
このフェーズは「貯める」ところまで。読む側（一覧表示・Markdown 出力など）は未着手。

## 取得対象

| type | 取得先 | 設定キー | DB の source 列 |
|---|---|---|---|
| `zenn` | `https://zenn.dev/topics/{tag}/feed`（RSS） | `tag` | `zenn:{tag}` |
| `qiita` | `https://qiita.com/tags/{tag}/feed`（Atom） | `tag` | `qiita:{tag}` |
| `github_releases` | `https://api.github.com/repos/{repo}/releases`（JSON） | `repo` | `github:{repo}` |

現在の対象は Zenn の `claudecode`、Qiita の `ClaudeCode`、GitHub の `anthropics/claude-code`。
3 つとも認証なしで取得できる。

## ゴール / ノンゴール

**ゴール**
- `news-collector` コマンドで、設定した全ソースから記事を集めて SQLite に入れる。
- 毎週実行しても、同じ記事が重複しない。
- 1 つのソースが失敗しても、残りを続ける。
- テストはネットワークに接続せず、モックで動く。

**ノンゴール（このフェーズでは作らない）**
- 週報の表示・出力（一覧、Markdown など）
- 常駐・スケジューリング（月曜の起動は、cron やタスクスケジューラに任せる）
- 記事本文の全文取得、既存記事の更新追従

## 構成

```
news-collector (cli.py)
  ├─ load_config()      config.toml を読み、検証する           config.py
  ├─ fetch_articles()   ソースごとに取得して Article にする    sources.py
  └─ Database.save()    URL をキーに、新規分だけ保存する       db.py
```

- 取得対象の追加は、`sources.py` に取得関数を足し、`config.py` の `_TARGET_KEY` と `_LABEL_PREFIX` に type を登録する。
- ネットワーク通信は `httpx.Client` を `fetch_articles()` に渡す形にしてある。テストではこれを `httpx.MockTransport` に差し替える。
- Zenn / Qiita のフィード解析は `feedparser`、GitHub は JSON をそのまま読む。

## 設定（config.toml）

```toml
[database]
path = "data/news.db"      # config.toml のあるフォルダからの相対パス

[[sources]]
type = "zenn"
tag = "claudecode"
```

- 設定ファイルは `--config` で指定。省略時はカレントの `./config.toml`。
- `[[sources]]` が 0 件、未知の `type`、必須キー（`tag` / `repo`）の欠落、`database.path` の欠落は設定エラー。
- DB のパスは、起動した場所ではなく設定ファイルの場所から解決する。cron などで別の場所から起動しても、同じ DB を使うため。
- DB のフォルダ（`data/` など）がなければ、起動時に作る。

## データ

テーブル `articles`:

| 列 | 内容 |
|---|---|
| `id` | 主キー |
| `url` | 記事の URL。`UNIQUE`。重複判定のキー |
| `source` | `zenn:claudecode` などの取得元ラベル |
| `title` | タイトル。GitHub は release 名、空なら tag 名 |
| `published_at` | 公開日時。UTC の ISO 8601（例: `2026-10-31T09:21:22+00:00`）。不明なら NULL |
| `summary` | 要約。先頭 300 文字。なければ空文字 |
| `fetched_at` | 取得した日時（UTC） |

- 同じ URL の記事は 2 回目以降は無視する（先に入った内容を保つ。更新は追わない）。
- 公開日時を UTC に統一しているので、ソースをまたいで文字列のまま並べ替えられる。

## 失敗の扱い

- 取得・解析・保存のどこで例外が起きても、そのソースだけを失敗として標準エラーに出し、次のソースへ進む。
- 失敗とみなすもの: 通信エラー、HTTP エラー、フィードとして解釈できない応答（HTML など）、リリース一覧でない JSON。
- 記事が 0 件でも、正しい応答なら成功。

| 終了コード | 意味 |
|---|---|
| 0 | 1 つ以上のソースが成功 |
| 1 | 全ソースが失敗 |
| 2 | 設定エラー（取得は行わない） |

## テスト

- pytest。ネットワークは使わず、`httpx.MockTransport` で応答を差し替える。
- fixture（`tests/sample_data.py`）は、実際のフィードと同じ構造にしてある。
- 範囲: DB の保存と重複排除、設定の検証、各ソースの変換、CLI の失敗継続と終了コード。
- 開発は TDD（失敗するテスト → 実装）で進めた。

## 設計上の判断

ユーザーが決めたこと:
- 対象は上の 3 つ、言語は Python、テストは pytest。
- コマンド名は `news-collector`。
- 1 つ失敗しても続け、全部失敗したら終了コード 1。
- 取得対象は `config.toml` で設定する。
- DB の場所は `data/news.db`。
- テストのネットワークはモックを使う。

Claude の判断:
- URL をキーにした重複排除、公開日時の UTC 統一、要約 300 文字。
- 設定エラーの終了コード 2、DB パスを設定ファイル基準にすること。
- ライブラリは `httpx` と `feedparser`。

## 既知の制限

- GitHub API は認証なしのため、1 時間あたりの回数制限がある（週 1 回の実行では問題にならない想定）。
- 取得するのは各フィードが返す直近の分だけ（Zenn 20 件、Qiita 4 件、GitHub 30 件程度）。実行間隔が長いと取りこぼす可能性がある。
- フィード内に URL のない記事があると、そのソース全体が失敗になる（未対応）。
