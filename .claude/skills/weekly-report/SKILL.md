---
name: weekly-report
description: 直近 7 日にためた記事（data/news.db）を週報にまとめ、HTML と一覧ページまで作って PR を出したいときに使う。「週報」「weekly report」「今週のまとめ」と言われたときが対象。実行すると、md・HTML・一覧の更新・コミット・PR 作成まで一括で行う。
---

# weekly-report

`data/news.db` の直近 7 日の記事をテーマ別にまとめ、代表記事は本文を調べて要約する。
`weekly/YYYY-MM-DD.md` → `weekly/YYYY-MM-DD.html` → `weekly/index.html` の更新 → ブランチ・コミット・PR まで、一括で行う。
`YYYY-MM-DD` は実行日（今日の日付）。このスキルの実行は、コミットと PR 作成の依頼を含む。

## 手順

### 0. 前提を確かめる
- `weekly/_template.html` と `weekly/index.html` があること。なければ、作らずに止めて、ユーザーに伝える（週報の PR が main に入っていない可能性がある）
- `git status` で、いまの変更を確かめる。手順 7 で add するのは `weekly/` の 3 ファイルだけ。ほかの未コミットの変更は触らない

### 1. 記事を読む
`articles` テーブル（`url, source, title, published_at, summary, fetched_at`）を読み取り専用で引く。
`.env` などの秘密ファイルは読まない。

- 期間: `COALESCE(published_at, fetched_at)` が実行日の 7 日前以降
- `published_at` の書式が ISO でない行があるときは、Python 側で日付に直してから絞る
- 一時スクリプトは `.scratchpad/` に置き、終わったら消す
- 0 件のときは、ファイルを作らず、その旨をユーザーに伝えて終わる

### 2. テーマに分ける
- 記事のタイトルと summary から、内容でテーマを決める（例: LLM・AI、言語・ツール、リリース情報）。`source`（Zenn / Qiita / GitHub Releases）は分け方にしない
- テーマは 3〜6 個。1 件だけのテーマは「その他」にまとめる
- 1 つの記事は 1 つのテーマにだけ入れる

### 3. 代表記事を選んで中身を調べる
テーマごとに、そのテーマを代表する記事を 3 つ選ぶ（記事が 3 件以下のテーマは全件）。

- 選ぶ基準: そのテーマの中心的な話題を扱っている。同じ著者・同じ話題に偏らせない
- 本文を読む: 記事の URL を WebFetch で取得して読む。取れないときは、`get_article` や DB の `summary` で代わりにし、その旨を要約の末尾に書く
- 要約は 3〜5 文。何が問題か・何をしたか・結果や結論、の順で、本文に書いてあることだけを書く
- 取得した本文は `.scratchpad/` に置いてよいが、終わったら消す

### 4. md を書く
`weekly/` がなければ作る。同じ日付のファイルが既にあるときは、上書きの前に対象を伝えて確認する。

```markdown
# 週報 YYYY-MM-DD

対象期間: YYYY-MM-DD 〜 YYYY-MM-DD ／ 記事 N 件

## <テーマ名>（N件）

<そのテーマの動きを 1〜2 文で>

### 代表記事

#### [記事タイトル](URL)
出どころ ／ 要約（3〜5 文）

### その他の記事

- [記事タイトル](URL) — 出どころ、1 行の要点
```

- 本文は日本語。タイトルは原文のまま
- 代表記事の要約は手順 3 で読んだ本文から、その他の記事の要点は summary から書く。書いていないことを足さない
- セクションは件数の多い順。代表記事を除いた残りは「その他の記事」に入れる（残りがなければ見出しごと省く）
- 出どころは `Zenn` / `Qiita` / `GitHub Releases` のいずれかで書く（HTML の色分けがこの文字に依存する）
- 上の書式を崩さない。HTML への変換スクリプトがこの書式を読む

### 5. HTML と一覧ページを作る
リポジトリ直下で、md と `weekly/_template.html` から HTML を作り、`weekly/index.html` に一覧のカードを足す。

```bash
.venv/Scripts/python -I .claude/skills/weekly-report/scripts/build_html.py YYYY-MM-DD
```

- 同じ日付のカードが一覧にあるときは、カードは変更されない
- `md の形式が想定と違います` と出たら、md の書式を直して再実行する
- 見た目を変えたいときは `_template.html`（と `index.html`）を直す。スクリプトに見た目を書かない

### 6. 確かめる
- md の記事数（代表記事＋その他）が、手順 1 の件数と一致することを実際に数えて示す
- md と HTML の全 URL が、DB の記事と過不足なく一致し、重複がないことを確かめる
- 各テーマの代表記事が 3 つ（または全件）あることを確かめる
- HTML の代表記事カード数・その他の記事数が md と一致し、`{{` が残っていないことを確かめる
- `weekly/index.html` のリンク先ファイルが存在することを確かめる
- ブラウザで開いて見た目を確かめていないときは、PR にそう書く

### 7. ブランチを切って PR を作る
**main に直接 push しない。** コミットと PR の説明は日本語で簡潔に書き、システムの指示にある帰属の行を末尾に付ける。

1. `git switch main` → `git pull --ff-only` → `git switch -c docs/weekly-YYYY-MM-DD`（同名のブランチがあるときは、ユーザーに確認する）
2. `git add weekly/YYYY-MM-DD.md weekly/YYYY-MM-DD.html weekly/index.html`（この 3 つだけ）
3. `git commit`（例: `docs: YYYY-MM-DD の週報を追加`）
4. `git push -u origin docs/weekly-YYYY-MM-DD`
5. `gh pr create --base main`。本文には、概要（対象期間・記事数・テーマ数）と、手順 6 の確認結果を書く
6. PR の URL をユーザーに伝える

### 8. 後片付けと報告
- `.scratchpad/` に自分が作ったファイルを消す（元からあるものは触らない）
- 次をユーザーに伝える: 作ったファイル、PR の URL、確認できたことと確認できていないこと
- 公開（GitHub Pages）は、PR が main にマージされたあとに、Pages のワークフローで行われる。マージはユーザーが行う
