# 28teamworks MCP 接続手順

TeamWorks を Claude Code / Claude Desktop から**自然言語で操作**するための MCP 設定手順です。

提供ツール（6 個）: `list_tasks` / `add_task` / `update_task_status` / `delete_task` / `get_weekly_report` / `list_projects`

接続方法は2つあります。**通常は「方法A（HTTP接続）」を使ってください**（clone も Python 環境も不要）。

---

## 方法A: HTTP 接続（推奨・全メンバー向け）

サーバー側に MCP が常駐しているため、各自の PC には**何もインストール不要**です。

### 手順
1. ブラウザで TeamWorks（https://teamworks-app.azurewebsites.net ）にログイン。
2. 左サイドバー下部の **「🔌 MCP接続情報をコピー」** をクリック。
   → 設定 JSON（あなた専用の長期トークン入り）がクリップボードにコピーされます。
3. 貼り付け先:
   - **Claude Code**: プロジェクト直下に `.mcp.json` を作成して貼り付け（または `claude mcp add-json 28teamworks '<コピー内容>'`）。
   - **Claude Desktop**: `%APPDATA%\Claude\claude_desktop_config.json`（mac: `~/Library/Application Support/Claude/claude_desktop_config.json`）に貼り付け。
4. Claude Code を開き直す / Claude Desktop を再起動。

### コピーされる内容（例）
```json
{
  "mcpServers": {
    "28teamworks": {
      "type": "http",
      "url": "https://teamworks-app.azurewebsites.net/mcp",
      "headers": { "Authorization": "Bearer <あなた専用の長期トークン>" }
    }
  }
}
```

### 補足
- トークンは **365 日有効**。期限切れになったら、再度ボタンでコピーし直してください。
- トークンは**あなたのアカウント権限**で動作します（テナント隔離・非表示タスクのルールはサーバー側で維持）。
- トークンは設定ファイルに**平文**で保存されます。ファイルの共有に注意してください。
- この接続は**本番データを直接操作**します（タスク追加・削除・状態変更）。

---

## 方法B: stdio 接続（ローカル開発者向け・上級）

リポジトリを clone してローカルで `mcp_server.py`（stdio 版）を起動する方法です。
開発時に**ローカルの API** を叩きたい場合に使います。

### 前提
1. `git clone https://github.com/wzy-octopus/team-works.git`
2. `uv` をインストール（PATH を通す）
3. `cd team-works/backend` → `uv sync`
4. 呼び出し先 API を起動: `uv run uvicorn app.main:app --reload`（`http://localhost:8000`）

### 設定（Claude Desktop / Claude Code）
```json
{
  "mcpServers": {
    "28teamworks": {
      "command": "uv",
      "args": ["--directory", "<clone した backend の絶対パス>", "run", "python", "mcp_server.py"],
      "env": {
        "TEAMWORKS_EMAIL": "<自分のメールアドレス>",
        "TEAMWORKS_PASSWORD": "<自分のパスワード>",
        "TEAMWORKS_API_URL": "http://localhost:8000"
      }
    }
  }
}
```

### 補足
- `<clone した backend の絶対パス>` は各自の環境に合わせる（Windows はバックスラッシュを `\\` にエスケープ）。
- `TEAMWORKS_API_URL` を本番 URL にすると本番データを操作する。
- `mcp_server.py`（stdio）は各自の PC で動くため、clone と `uv sync` が必要。

---

## 動作確認

API 起動状態（方法A は常時稼働、方法B はローカル起動）で、Claude に次のように頼む:
- 「list_projects を実行して」 → プロジェクト一覧
- 「今日のタスクを見せて」 → `list_tasks`
- 「『要件定義』というタスクを 2 時間で追加して」 → `add_task`
