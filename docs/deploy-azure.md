# Azure 手動デプロイ手順

Azure App Service (Linux) への手動デプロイ手順。  
所要時間：初回 約1〜2時間、2回目以降 約20分。

---

## 前提条件

- Azure サブスクリプションあり
- ローカルで `uv`・`node` が使える状態
- [azure.com](https://portal.azure.com) にログイン済み

---

## Step 1 — デプロイ用 ZIP を作成（ローカル作業）

### 1-1. requirements.txt を生成

```bash
cd backend
uv export --no-hashes -o requirements.txt
```

### 1-2. フロントエンドをビルドして配置

```bash
cd ../frontend
npm run build
cp -r dist/ ../backend/static/
```

### 1-3. ZIP を作成

`backend/` フォルダの**中身**を ZIP のルートに入れる（フォルダごと圧縮しない）。

**Windows の場合：**  
`backend/` フォルダを開き、中のファイル・フォルダを全選択 → 右クリック → 「圧縮」。  
`.venv/` は含めない（あれば手動で除外する）。

**コマンドで行う場合：**

```bash
cd backend
zip -r ../deploy.zip . \
  --exclude ".venv/*" \
  --exclude "__pycache__/*" \
  --exclude "*.pyc" \
  --exclude "*.db"
```

ZIP 内の構造（これが正しい形）：

```
deploy.zip
├── app/
│   ├── main.py
│   ├── core/
│   ├── models/
│   ├── routers/
│   ├── schemas/
│   └── services/
├── static/          ← React ビルド成果物
│   ├── index.html
│   └── assets/
├── alembic/
├── requirements.txt
├── pyproject.toml
└── alembic.ini
```

---

## Step 2 — App Service を作成（Azure Portal）

1. [portal.azure.com](https://portal.azure.com) → **「リソースの作成」**
2. 「Web アプリ」を選択
3. 以下の設定で作成：

| 項目 | 値 |
|---|---|
| リソース グループ | 新規作成 or 既存を選択 |
| 名前 | `28teamworks`（任意。URL になる） |
| ランタイム スタック | **Python 3.12** |
| OS | **Linux** |
| リージョン | Japan East |
| App Service プラン | **B1**（Basic、月 ¥1,800 程度） |

4. 「確認および作成」→「作成」

---

## Step 3 — 環境変数を設定（Azure Portal）

作成した App Service を開く →  
左メニュー **「設定」→「環境変数」** → 以下を追加。

| 名前 | 値 |
|---|---|
| `DATABASE_URL` | `sqlite+aiosqlite:////home/data/app.db` |
| `SECRET_KEY` | ランダムな長い文字列（例：`openssl rand -hex 32` の出力）|
| `ALLOWED_ORIGINS` | `https://<your-app>.azurewebsites.net` |
| `ANTHROPIC_API_KEY` | Anthropic API キー |
| `SCM_DO_BUILD_DURING_DEPLOYMENT` | `true` |

> **AI を Azure AI Foundry 経由で使う場合は代わりに以下を設定：**
>
> | 名前 | 値 |
> |---|---|
> | `LLM_BACKEND` | `foundry` |
> | `FOUNDRY_API_KEY` | Foundry の API キー |
> | `FOUNDRY_ENDPOINT` | `https://<resource>.services.ai.azure.com/anthropic/` |
> | `FOUNDRY_MODEL` | `claude-sonnet-4-5` |

設定後、「適用」をクリック。

---

## Step 4 — スタートアップ コマンドを設定

左メニュー **「設定」→「構成」→「全般設定」タブ**

**スタートアップ コマンド** 欄に入力：

```
mkdir -p /home/data && uvicorn app.main:app --host 0.0.0.0 --port 8000
```

「保存」をクリック。

---

## Step 5 — ZIP をアップロード（Kudu）

1. 左メニュー **「開発ツール」→「高度なツール (Kudu)」→「移動」**
2. Kudu が開いたら、ブラウザの URL 末尾を `/ZipDeployUI` に書き換えて Enter

   ```
   https://<your-app>.scm.azurewebsites.net/ZipDeployUI
   ```

3. Step 1 で作った ZIP ファイルをページにドラッグ＆ドロップ
4. デプロイログが流れ、`Deployment successful` が出れば完了

---

## Step 6 — DB 初期化（初回のみ）

Kudu の **「デバッグ コンソール」→「CMD」** を開いて実行：

```bash
cd /home/site/wwwroot
python -m alembic upgrade head
```

シードデータが必要な場合はここで seed スクリプトも実行する。

---

## Step 7 — 動作確認

ブラウザで `https://<your-app>.azurewebsites.net` を開く。  
React の画面が表示され、ログインできれば完了。

---

## 2回目以降のデプロイ

Step 1 の ZIP 作成 → Step 5 の Kudu アップロードのみでよい。  
環境変数・スタートアップ コマンドは変更がなければ不要。

```bash
# ショートカット：フロント再ビルド + ZIP 作成
cd frontend && npm run build && cp -r dist/ ../backend/static/
cd ../backend && zip -r ../deploy.zip . --exclude ".venv/*" --exclude "__pycache__/*" --exclude "*.pyc" --exclude "*.db"
```

---

## トラブルシューティング

| 症状 | 確認箇所 |
|---|---|
| 画面が真っ白 | Kudu の `LogFiles/` でエラーログを確認 |
| 500 エラー | App Service の「ログ ストリーム」でスタックトレースを確認 |
| `ModuleNotFoundError` | `SCM_DO_BUILD_DURING_DEPLOYMENT=true` が設定されているか確認 |
| DB ファイルが消える | `DATABASE_URL` が `/home/data/` を向いているか確認（`/home` は永続） |
| ログイン後に弾かれる | `SECRET_KEY` と `ALLOWED_ORIGINS` が正しく設定されているか確認 |
