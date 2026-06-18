# 技術スタック定義書

## アーキテクチャ概要

```
┌─────────────────────────────────────────────────────┐
│                    Azure App Service                 │
│                                                     │
│  ┌──────────────────┐    ┌───────────────────────┐  │
│  │  Frontend        │    │  Backend              │  │
│  │  React (Vite)    │◄──►│  FastAPI (Python)     │  │
│  │  Static Files    │    │                       │  │
│  └──────────────────┘    └──────────┬────────────┘  │
│                                     │               │
│                          ┌──────────▼────────────┐  │
│                          │  SQLite               │  │
│                          │  (prototype)          │  │
│                          └───────────────────────┘  │
└─────────────────────────────────────────────────────┘
          │                        │
          ▼                        ▼
   Slack / Teams Bot         Anthropic Claude API
   (外部チャット連携)          (AI週報サマリ生成)
          │
          ▼
   MCP Server
   (Claude Desktop連携)
```

---

## レイヤー別スタック

### フロントエンド

| 項目 | 採用技術 | 理由 |
|---|---|---|
| フレームワーク | **React 19** | コンポーネント設計・状態管理のエコシステムが豊富 |
| ビルドツール | **Vite** | 高速HMR。Azure Static Web Appsへのデプロイが容易 |
| 言語 | **TypeScript** | 型安全でAPIレスポンスの型定義と連携しやすい |
| スタイリング | **Tailwind CSS** | デザインプロトタイプのCSS変数との親和性が高い |
| ルーティング | **React Router v7** | SPA内のページ遷移 |
| APIクライアント | **TanStack Query + axios** | キャッシュ・ローディング状態管理 |
| 状態管理 | **Zustand** | 軽量。テナント・プロジェクト選択状態などグローバル状態の管理 |

---

### バックエンド

| 項目 | 採用技術 | 理由 |
|---|---|---|
| フレームワーク | **FastAPI** | 高速・自動APIドキュメント生成（Swagger UI）・型ヒント対応 |
| 言語 | **Python 3.12** | |
| ORM | **SQLAlchemy 2.x (async)** | 非同期対応・後でPostgreSQLへ切り替えやすい |
| マイグレーション | **Alembic** | SQLAlchemyと統合。DBスキーマのバージョン管理 |
| バリデーション | **Pydantic v2** | FastAPIに内蔵。リクエスト/レスポンスの型定義 |
| 認証 | **python-jose + passlib** | JWT生成・パスワードハッシュ |
| SSO (OAuth2) | **Authlib** | Google/Microsoft OAuthフロー |
| スケジューラ | **APScheduler** | 週次AI週報生成の定期実行（毎週金曜EOD） |
| パッケージ管理 | **uv** | 高速・lock file管理。pip/poetryの後継 |

---

### データベース

| 環境 | 採用技術 | 備考 |
|---|---|---|
| プロトタイプ | **SQLite** | ファイルベース。Azure App Service の永続ストレージにマウント |
| 本番移行時 | **Azure Database for PostgreSQL** | SQLAlchemy の接続文字列変更のみで移行可能 |

**SQLite on Azure App Service の注意点**
- App Service の `/home` ディレクトリは永続マウントされるため、DBファイルを `/home/data/` 以下に配置する
- スケールアウト（インスタンス複数化）時はSQLiteが競合するため、本番では PostgreSQL に移行すること

---

### AI連携

| 項目 | 採用技術 | 用途 |
|---|---|---|
| 週報サマリ生成 | **Anthropic Claude API** (`claude-sonnet-4-6`) | タスク一覧を渡してサマリ文を生成 |
| SDK | **anthropic Python SDK** | プロンプトキャッシュを活用してコスト削減 |

**週報生成の処理フロー**
```
APScheduler（毎週金曜 18:00）
  → 対象ユーザーのタスク一覧を取得（is_private=false）
  → Claude API にタスク情報を渡してサマリ生成
  → weekly_reports.ai_summary に保存
  → Slack / Teams Bot 経由でユーザーに通知
```

---

### 外部チャット連携

| 項目 | 採用技術 | 用途 |
|---|---|---|
| Slack Bot | **slack-bolt (Python)** | タスク登録・照会・通知 |
| Teams Bot | **Microsoft Bot Framework SDK** | 同上 |

**Botの主なコマンド**
```
「今日は要件定義2時間、コードレビュー1時間やります」
  → 自然言語解析（Claude API）→ タスクを自動登録

「今日のタスクを教えて」
  → 当日のタスク一覧を返信

「週報を確認して」
  → 最新の週報ドラフトを返信
```

---

### MCP サーバー（Claude Desktop 連携）

| 項目 | 内容 |
|---|---|
| プロトコル | Model Context Protocol (MCP) |
| 実装 | FastAPI エンドポイントとして実装。または独立したMCPサーバーとして分離 |
| 主なツール | `add_task` / `list_tasks` / `complete_task` / `get_weekly_report` |

---

### インフラ（Azure）

| リソース | サービス | 用途 |
|---|---|---|
| アプリ実行 | **Azure App Service (Linux)** | FastAPI + React 静的ファイルを同一Appで配信 |
| シークレット管理 | **Azure Key Vault** | APIキー・OAuthシークレット・JWT秘密鍵 |
| ログ | **Azure Monitor / Application Insights** | エラー追跡・パフォーマンス監視 |
| CI/CD | **GitHub Actions** | main ブランチへのプッシュで自動デプロイ |

**App Service の構成（プロトタイプ）**
```
Azure App Service (B1プラン)
  ├─ /home/site/wwwroot/   ← FastAPIアプリ
  ├─ /home/data/app.db     ← SQLiteファイル（永続）
  └─ /home/site/wwwroot/static/  ← Reactビルド成果物
```

---

## プロジェクト構成

```
28teamworks/
├── backend/
│   ├── app/
│   │   ├── main.py            # FastAPIエントリーポイント
│   │   ├── core/
│   │   │   ├── config.py      # 環境変数・設定
│   │   │   ├── security.py    # JWT・パスワードハッシュ
│   │   │   └── database.py    # DB接続・セッション
│   │   ├── models/            # SQLAlchemyモデル
│   │   ├── schemas/           # Pydanticスキーマ
│   │   ├── routers/           # APIルーター（機能別）
│   │   │   ├── auth.py
│   │   │   ├── tasks.py
│   │   │   ├── weekly_reports.py
│   │   │   └── admin.py
│   │   ├── services/          # ビジネスロジック
│   │   │   ├── ai_summary.py  # Claude API呼び出し
│   │   │   └── scheduler.py   # 週次バッチ処理
│   │   └── integrations/
│   │       ├── slack.py
│   │       └── teams.py
│   ├── alembic/               # DBマイグレーション
│   ├── tests/
│   ├── pyproject.toml         # uv管理
│   └── .env.example
├── frontend/
│   ├── src/
│   │   ├── pages/             # 画面コンポーネント
│   │   ├── components/        # 共通UIコンポーネント
│   │   ├── hooks/             # カスタムフック
│   │   ├── stores/            # Zustandストア
│   │   └── lib/               # APIクライアント・ユーティリティ
│   ├── package.json
│   └── vite.config.ts
├── design/                    # HTMLプロトタイプ（参照用）
├── docs/                      # 各種定義書
└── .github/workflows/         # CI/CD
    └── deploy.yml
```

---

## 環境変数

```env
# App
APP_ENV=development          # development / production
SECRET_KEY=                  # JWT署名キー（Azure Key Vaultで管理）
DATABASE_URL=sqlite+aiosqlite:////home/data/app.db

# Anthropic
ANTHROPIC_API_KEY=

# OAuth
GOOGLE_CLIENT_ID=
GOOGLE_CLIENT_SECRET=
MICROSOFT_CLIENT_ID=
MICROSOFT_CLIENT_SECRET=

# Slack
SLACK_BOT_TOKEN=
SLACK_SIGNING_SECRET=

# Teams
TEAMS_APP_ID=
TEAMS_APP_PASSWORD=
```

---

## 開発環境のセットアップ手順（概要）

```bash
# バックエンド
cd backend
uv sync
uv run alembic upgrade head
uv run uvicorn app.main:app --reload

# フロントエンド
cd frontend
npm install
npm run dev
```

---

## プロトタイプ → 本番への移行ポイント

| 項目 | プロトタイプ | 本番 |
|---|---|---|
| DB | SQLite | Azure Database for PostgreSQL |
| スケジューラ | APScheduler（アプリ内） | Azure Functions または Container Jobs |
| 認証シークレット | .env ファイル | Azure Key Vault |
| App Service プラン | B1（1コア・1.75GB） | P1v3以上（オートスケール対応） |
| フロント配信 | App Serviceの静的ファイル | Azure Static Web Apps（分離推奨） |
