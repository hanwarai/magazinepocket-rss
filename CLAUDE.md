# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

週刊少年マガジンポケット（pocket.shonenmagazine.com）の無料エピソードを取得し、Atom RSSフィードとして配信するジェネレーター。GitHub Actionsで12時間ごとに自動実行され、GitHub Pagesとして公開される。

## Commands

```bash
# 依存パッケージインストール
uv sync --all-extras

# フィード生成（main.pyを実行）
uv run main.py

# SSL検証を無効にして実行（開発・デバッグ用）
SSL_VERIFY=false uv run main.py

# テスト実行（requests-mock で I/O モック）
uv run pytest

# 型検査（CI ゲート）
uv run mypy main.py
```

## Architecture

```
feed.csv → main.py → feeds/*.xml + feeds/index.html → GitHub Pages
```

**処理フロー（main.py）:**
1. `feed.csv` からマンガIDを読み込む
2. `https://pocket.shonenmagazine.com/title/{id}` をスクレイピングしてタイトル・説明を取得（BeautifulSoup4）
3. SHA256/SHA512ベースの認証ハッシュを生成（`mc`, `vh`, `Od`, `wh`, `Ae` 関数）
4. `https://api.pocket.shonenmagazine.com/episode/list` にPOSTリクエストを送りエピソード一覧を取得
5. `point == 0` の無料エピソードのみをAtom RSSフィードとして `feeds/{id}.xml` に出力（feedgenerator）
6. Jinja2テンプレート（`templates/index.html`）で `feeds/index.html` を生成

**主要ファイル:**
- `main.py` — 全処理ロジック（スクレイピング・ハッシュ生成・API呼び出し・フィード生成）
- `feed.csv` — トラッキング対象マンガIDのリスト（1列）
- `templates/index.html` — Jinja2テンプレート（Bootstrap 5使用）
- `feeds/` — 生成ファイル出力先（gitignore済み、`.gitkeep`のみ管理）

## CI/CD

GitHub Actions（`.github/workflows/gh-pages.yaml`）:
- トリガー: mainブランチへのpush、12時間ごとのスケジュール実行
- 処理: `uv sync --locked --all-extras` → `uv run mypy main.py` → `uv run pytest` → `uv run main.py` → `feeds/` を GitHub Pages にデプロイ
- scheduled run が失敗した場合、`notify-failure` ジョブが `ci-failure` ラベルの Issue を自動起票（既存 open Issue があればコメント追記）

GitHub Actions（`.github/workflows/ci.yaml`）:
- トリガー: pull_request
- 処理: `uv sync --locked --all-extras` → `uv run mypy main.py` → `uv run pytest`
- PR 用の軽量ゲート。`main.py` のスクレイピングと Pages デプロイは行わない

共通部品:
- `.github/scripts/resolve-uv-version.sh` — `pyproject.toml` の uv ピンを読み `version=X.Y.Z` を出力する。両ワークフローが使う。仕様は `tests/test_resolve_uv_version.py` が固定しており、ローカルでも実行できるよう `grep -P`（GNU 限定）ではなく POSIX `sed` で書いてある
- `uv sync` は両方とも `--locked`。`pyproject.toml` を編集して `uv lock` を忘れた場合に CI が落ちる
- **setup-uv / setup-python などの `uses:` 行を composite action（`.github/actions/*/action.yml`）へ切り出してはいけない**。Dependabot の github-actions エコシステムは `.github/workflows/` とリポジトリルートの `action.yml` しか走査せず、そこへ移すとバージョン追跡から外れる（dependabot-core#9788 は "not planned" で close）。`uses:` 行の重複は Dependabot が自動で同期するため許容する

## Notes

- パッケージマネージャーは `uv` を使用（`pip` は使わない）
- Python 3.13 が必要（`.python-version` で指定）
- APIへのリクエストにはカスタムヘッダー（`x-manga-hash`, `x-manga-is-crawler`）が必要
- `feeds/*.xml` と `feeds/index.html` は生成物のためgitignoreされている
- **`mc` / `vh` / `Od` / `wh` / `Ae` の API 検証ハッシュ関数は API サーバーが期待する値を生成するため、`tests/test_hash.py` のゴールデン値を破るリファクタは禁止**。実装を変える場合はゴールデン値が完全一致することを必ず確認する
- `read_feed_ids` は数字のみの ID を許可し、重複は自動除去（パストラバーサル防止）
