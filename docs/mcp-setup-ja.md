# 28teamworks MCP サーバー設定手順

## これは何か

`backend/mcp_server.py` は、28teamworks の API を**自然言語で操作する**ための MCP サーバーです。
Claude Desktop / Claude Code に登録すると、「今日のタスクは？」「タスクを追加して」などの会話で
タスク管理・週報照会ができます。

提供ツール（6 個）:

| ツール | 機能 |
|---|---|
| `list_tasks` | 指定日のマイタスク一覧 |
| `add_task` | タスク追加 |
| `update_task_status` | ステータス変更（todo / in_progress / done） |
| `delete_task` | タスク削除 |
| `get_weekly_report` | 週報取得 |
| `list_projects` | プロジェクト一覧 |

> 補足: MCP サーバー自体は API の**クライアント**です。LLM の API キーは不要で、
> あなたのログイン情報で `/api/auth/login` してトークンを取り、各 API を呼びます。

---

## 前提条件

1. **uv** がインストール済みで PATH に通っていること
2. backend の依存が入っていること: `cd backend` → `uv sync`
3. **呼び出し先の API が起動していること**（mcp_server.py は API を叩くだけなので、API が無いと全ツールがエラー）
   - ローカル: `uv run uvicorn app.main:app --reload` → `http://localhost:8000`
   - 本番を使う場合: `TEAMWORKS_API_URL=https://teamworks-app.azurewebsites.net`

---

## 環境変数

| 変数 | 必須 | 説明 | 既定値 |
|---|---|---|---|
| `TEAMWORKS_EMAIL` | ✅ | ログイン用メールアドレス | — |
| `TEAMWORKS_PASSWORD` | ✅ | パスワード | — |
| `TEAMWORKS_TENANT_ID` | 任意 | テナントID | 省略時は最初のテナント |
| `TEAMWORKS_API_URL` | 任意 | API のベース URL | `http://localhost:8000` |

---

## A. Claude Desktop に登録する場合

設定ファイル（Windows）: `%APPDATA%\Claude\claude_desktop_config.json`
（Claude Desktop アプリ → 設定 → 開発者 → 「構成を編集」からも開けます）

```json
{
  "mcpServers": {
    "28teamworks": {
      "command": "uv",
      "args": [
        "--directory",
        "C:\\Programming\\28teamworks\\backend",
        "run",
        "python",
        "mcp_server.py"
      ],
      "env": {
        "TEAMWORKS_EMAIL": "wang.ziyang@mct-japan.co.jp",
        "TEAMWORKS_PASSWORD": "＜あなたのパスワード＞",
        "TEAMWORKS_API_URL": "http://localhost:8000"
      }
    }
  }
}
```

1. 上記を保存
2. Claude Desktop を**再起動**
3. 入力欄の 🔌（ツール）アイコンに `28teamworks` のツールが表示されれば成功

---

## B. Claude Code に登録する場合

### 方法1: プロジェクト直下に `.mcp.json` を置く（チーム共有向け）

`C:\Programming\28teamworks\.mcp.json` を新規作成し、上の A と**同じ内容**を書く。
Claude Code を開き直すと自動で読み込まれます。

### 方法2: CLI で追加する

```powershell
claude mcp add 28teamworks `
  -e TEAMWORKS_EMAIL=wang.ziyang@mct-japan.co.jp `
  -e "TEAMWORKS_PASSWORD=＜あなたのパスワード＞" `
  -e TEAMWORKS_API_URL=http://localhost:8000 `
  -- uv --directory C:\Programming\28teamworks\backend run python mcp_server.py
```

確認: `claude mcp list`

---

## 動作確認

API を起動した状態で、Claude に次のように頼む:

- 「list_projects を実行して」 → プロジェクト一覧が返る
- 「今日のタスクを見せて」 → `list_tasks` が動く
- 「『要件定義』というタスクを 2 時間で追加して」 → `add_task` が動く

---

## 注意点

- **API が起動していないとツールはエラー**になります（mcp_server.py は API のクライアント）。
- `TEAMWORKS_API_URL` を本番 URL にすると、**本番データを直接操作**します。テスト時はローカルを推奨。
- パスワードが**平文**で設定ファイルに入るため、ファイルの取り扱いに注意してください。
- `--directory` のパスは**自分の環境の backend パス**に合わせて変更してください
  （この手順書では `C:\Programming\28teamworks\backend` を例にしています）。
- `TEAMWORKS_TENANT_ID` は通常省略で OK（最初の所属テナントが使われます）。
