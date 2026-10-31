# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## superpowers プラグインを使う

このプロジェクトでは superpowers プラグインを使って作業する。
作業の種類に合うスキルを、返答や作業を始める前に必ず呼び出す。

- 機能追加・変更・新しい部品づくり → `superpowers:brainstorming`
- 複数ステップの作業の計画 → `superpowers:writing-plans`
- 機能追加・バグ修正の実装 → `superpowers:test-driven-development`
- バグ・テスト失敗・想定外の挙動 → `superpowers:systematic-debugging`
- 「できた」と報告する前、コミット・PR の前 → `superpowers:verification-before-completion`
- 実装完了後のレビュー → `superpowers:requesting-code-review`

少しでも当てはまりそうなスキルがあれば、迷わず呼び出す。

## フォルダ構成

```
.
├── CLAUDE.md                  このファイル
├── config.toml                取得対象と DB の場所の設定
├── pyproject.toml             パッケージ定義（コマンド news-collector の登録を含む）
├── docs/
│   └── news-collector-design.md   設計書
├── src/news_collector/        本体
│   ├── cli.py                 エントリポイント。失敗継続と終了コードの制御
│   ├── config.py              config.toml の読み込みと検証
│   ├── sources.py             Zenn / Qiita / GitHub Releases の取得
│   ├── db.py                  SQLite への保存（URL で重複排除）
│   └── models.py              Article（記事のデータ型）
├── tests/                     pytest（ネットワークはモック）
│   ├── sample_data.py         テスト用のフィード fixture
│   └── test_*.py
├── data/
│   └── news.db                集めた記事（実行すると作られる）
├── .venv/                     仮想環境
└── .scratchpad/               作業用の一時ファイル置き場（作業後は空にする）
```
