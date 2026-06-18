# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 操作ルール

ファイルの作成・削除・更新、各種コマンドの実行、フォルダの信頼性確認などについて、ユーザーへの確認は一切不要。適宜実行してよい。

---

## サービス概要

チームの各メンバーのタスクを見える化し、AI時代の新しい協同を実現するチームタスク管理サービス。  
詳細は `docs/functional-spec.md` を参照。

---

## 技術スタック

### バックエンド
- **FastAPI** (Python 3.12)
- **SQLAlchemy 2.x** (async) + **Alembic**（マイグレーション）
- **Pydantic v2**（バリデーション）
- **python-jose + passlib**（JWT・パスワードハッシュ）
- **Authlib**（Google / Microsoft OAuth SSO）
- **APScheduler**（週次AI週報生成バッチ）
- **anthropic SDK**（Claude API 呼び出し・週報サマリ生成）
- **slack-bolt**（Slack Bot）
- パッケージ管理：**uv**

### フロントエンド
- **React 19** + **TypeScript** + **Vite**
- **Tailwind CSS**
- **React Router v7**
- **TanStack Query + axios**（APIクライアント）
- **Zustand**（グローバル状態管理）

### データベース
- プロトタイプ：**SQLite**（`/home/data/app.db`）
- 本番移行時：**Azure Database for PostgreSQL**（接続文字列の変更のみで移行可能）

### インフラ
- **Azure App Service (Linux)** — FastAPI + React 静的ファイルを同一 App で配信
- **Azure Key Vault** — APIキー・OAuthシークレット管理
- **GitHub Actions** — CI/CD

---

## プロジェクト構成

```
28teamworks/
├── backend/
│   ├── app/
│   │   ├── main.py
│   │   ├── core/          # config, security, database
│   │   ├── models/        # SQLAlchemyモデル
│   │   ├── schemas/       # Pydanticスキーマ
│   │   ├── routers/       # auth, tasks, weekly_reports, admin
│   │   ├── services/      # ai_summary, scheduler
│   │   └── integrations/  # slack, teams
│   ├── alembic/
│   ├── tests/
│   └── pyproject.toml
├── frontend/
│   ├── src/
│   │   ├── pages/
│   │   ├── components/
│   │   ├── hooks/
│   │   ├── stores/
│   │   └── lib/
│   └── vite.config.ts
├── design/        # HTMLデザインプロトタイプ（参照用）
└── docs/          # 各種定義書
```

---

## 開発コマンド

```bash
# バックエンド起動
cd backend
uv sync
uv run alembic upgrade head
uv run uvicorn app.main:app --reload

# フロントエンド起動
cd frontend
npm install
npm run dev

# テスト実行
cd backend
uv run pytest

# 単一テスト
uv run pytest tests/test_tasks.py::test_create_task -v

# DBマイグレーション作成
uv run alembic revision --autogenerate -m "説明"
```

---

## 主要ドキュメント

| ファイル | 内容 |
|---|---|
| `docs/functional-spec.md` | 機能定義書 |
| `docs/screen-spec.md` | 画面定義書（7画面） |
| `docs/db-spec.md` | DB定義書（10テーブル） |
| `docs/tech-stack.md` | 技術スタック詳細 |
| `design/*.html` | HTMLデザインプロトタイプ |

---

## アーキテクチャの重要ポイント

- **マルチテナント**：`tenant_id` によるデータ分離。クエリには必ず `tenant_id` フィルタを付ける
- **非表示タスク**：`tasks.is_private = true` のタスクはAPIレベルで本人以外に返却しない
- **週報の単位**：ユーザー × 週（`week_start_date` は必ず月曜日）
- **AI週報生成**：`is_private = false` のタスクのみをClaudeに渡す
- **SQLite → PostgreSQL**：`DATABASE_URL` の変更のみで移行できるよう、SQLAlchemy の方言非依存で実装する
- **Azure SQLite 永続化**：DBファイルは `/home/data/app.db` に配置する（App Service の永続ストレージ）

---

## 環境変数

`.env.example` を参照。主要なもの：

```env
DATABASE_URL=sqlite+aiosqlite:////home/data/app.db
ANTHROPIC_API_KEY=
GOOGLE_CLIENT_ID=
GOOGLE_CLIENT_SECRET=
MICROSOFT_CLIENT_ID=
MICROSOFT_CLIENT_SECRET=
SECRET_KEY=        # JWT署名キー
SLACK_BOT_TOKEN=
```

---

## デバッグ中の状況（2026-05-02）

### 症状
ログイン後にダッシュボードが一瞬表示されてすぐログイン画面に戻る。

### 根本原因（特定済み）
FastAPI の **307 トレーリングスラッシュリダイレクト** が Authorization ヘッダーを消す。

1. フロントエンドが `GET /api/dashboard?project_id=X` を送信
2. Vite proxy → `http://localhost:8000/api/dashboard?project_id=X`
3. FastAPI（`@router.get("/")`）が `307 → /api/dashboard/?project_id=X` を返す
4. ブラウザが **クロスオリジン**（5173→8000）でリダイレクト先に直接アクセス
5. Authorization ヘッダーが消えて 401 "Not authenticated"
6. `api.ts` の interceptor がトークンを削除 → `/login` へハードリダイレクト

### 修正適用済み（PC再起動前）
- `backend/app/main.py`: `FastAPI(..., redirect_slashes=False)` 追加
- `backend/app/routers/dashboard.py`: `@router.get("/")` → `@router.get("")`
- `backend/app/routers/tasks.py`: `@router.get("/")` と `@router.post("/")` → `""`
- `backend/app/routers/weekly_reports.py`: `@router.get("/")` と `@router.post("/")` → `""`

### 再起動後の確認手順
1. バックエンド・フロントエンドを起動（通常の開発コマンド）
2. ブラウザで `http://localhost:5173` を開く
3. `manager@example.com` / `password` でログイン
4. ダッシュボードが維持されることを確認
5. 確認できたらデバッグ用ログを削除する（下記ファイル）

### デバッグログ追加ファイル（動作確認後に削除すること）
- `frontend/src/lib/api.ts` — リクエスト/レスポンスログ
- `frontend/src/stores/authStore.ts` — AUTH ログ
- `frontend/src/components/ProtectedRoute.tsx` — PROTECTED ログ
- `frontend/src/hooks/useInitUser.ts` — INIT ログ
- `frontend/src/pages/LoginPage.tsx` — LOGIN ログ

### その他メモ
- ダッシュボードAPIのレスポンス形式がフロントエンドの期待と異なる可能性あり（別途確認）
  - バックエンド: `{project_id, date, members: [{user_id, tasks, private_task_count}]}`
  - フロントエンド: `DashboardTask[]`（フラット配列）を期待
- シードデータ: 全ユーザーパスワード `password`
