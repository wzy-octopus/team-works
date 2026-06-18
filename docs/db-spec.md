# DB定義書

## テーブル一覧

| テーブル名 | 概要 |
|---|---|
| tenants | テナント（企業・組織） |
| users | ユーザー |
| oauth_accounts | OAuth認証アカウント（SSO連携） |
| tenant_users | テナントへの所属・ロール・上長設定 |
| projects | プロジェクト |
| project_members | プロジェクトへの参加・プロジェクト内ロール |
| tasks | タスク |
| weekly_reports | 週間レポート |
| weekly_report_feedbacks | 上長フィードバック（コメント） |
| weekly_report_reactions | 上長フィードバック（リアクション） |

---

## ER概要

```
tenants
  └─< tenant_users >─ users
                         └─< oauth_accounts
  └─< projects
         └─< project_members >─ users
         └─< tasks >─ users

users ─< weekly_reports
              └─< weekly_report_feedbacks >─ users（上長）
                        └─< weekly_report_reactions
```

---

## テーブル定義

---

### tenants

| カラム名 | 型 | NULL | デフォルト | 説明 |
|---|---|---|---|---|
| id | UUID | NO | gen_random_uuid() | PK |
| name | VARCHAR(255) | NO | | 組織名（例：MCTジャパン株式会社） |
| domain | VARCHAR(255) | YES | | メールドメイン（SSO時の組織自動判定用。例：mct-japan.co.jp） |
| is_active | BOOLEAN | NO | true | 無効化フラグ |
| created_at | TIMESTAMP | NO | now() | |
| updated_at | TIMESTAMP | NO | now() | |

---

### users

| カラム名 | 型 | NULL | デフォルト | 説明 |
|---|---|---|---|---|
| id | UUID | NO | gen_random_uuid() | PK |
| email | VARCHAR(255) | NO | | メールアドレス。UNIQUE |
| name | VARCHAR(100) | NO | | 表示名 |
| password_hash | VARCHAR(255) | YES | | パスワード認証用ハッシュ。SSO専用ユーザーはNULL |
| created_at | TIMESTAMP | NO | now() | |
| updated_at | TIMESTAMP | NO | now() | |

**インデックス**
- UNIQUE (email)

---

### oauth_accounts

SSOプロバイダとの紐付け。1ユーザーがGoogle・Microsoft両方を持つことも可能。

| カラム名 | 型 | NULL | デフォルト | 説明 |
|---|---|---|---|---|
| id | UUID | NO | gen_random_uuid() | PK |
| user_id | UUID | NO | | FK → users.id |
| provider | ENUM | NO | | 'google' / 'microsoft' |
| provider_user_id | VARCHAR(255) | NO | | プロバイダ側のユーザーID |
| created_at | TIMESTAMP | NO | now() | |

**インデックス**
- UNIQUE (provider, provider_user_id)
- INDEX (user_id)

---

### tenant_users

テナントへの所属・テナントロール・週報送付先（上長）を管理する。

| カラム名 | 型 | NULL | デフォルト | 説明 |
|---|---|---|---|---|
| id | UUID | NO | gen_random_uuid() | PK |
| tenant_id | UUID | NO | | FK → tenants.id |
| user_id | UUID | NO | | FK → users.id |
| role | ENUM | NO | 'member' | 'admin' / 'manager' / 'member' |
| manager_user_id | UUID | YES | | FK → users.id。週報の送付先上長 |
| is_active | BOOLEAN | NO | true | 無効化・招待取消フラグ |
| last_login_at | TIMESTAMP | YES | | 最終ログイン日時 |
| created_at | TIMESTAMP | NO | now() | |
| updated_at | TIMESTAMP | NO | now() | |

**インデックス**
- UNIQUE (tenant_id, user_id)
- INDEX (tenant_id, role)

**備考**
- manager_user_id が NULL の場合は上長未設定（管理画面で警告表示）
- roleが 'admin' または 'manager' のユーザーは他メンバーの週報を閲覧できる

---

### projects

| カラム名 | 型 | NULL | デフォルト | 説明 |
|---|---|---|---|---|
| id | UUID | NO | gen_random_uuid() | PK |
| tenant_id | UUID | NO | | FK → tenants.id |
| name | VARCHAR(255) | NO | | プロジェクト名 |
| color | CHAR(7) | NO | '#6c63ff' | 表示カラー（HEXコード） |
| description | TEXT | YES | | 説明 |
| is_active | BOOLEAN | NO | true | アーカイブフラグ |
| created_at | TIMESTAMP | NO | now() | |
| updated_at | TIMESTAMP | NO | now() | |

**インデックス**
- INDEX (tenant_id, is_active)

---

### project_members

プロジェクトへの参加とプロジェクト内ロールを管理する。

| カラム名 | 型 | NULL | デフォルト | 説明 |
|---|---|---|---|---|
| id | UUID | NO | gen_random_uuid() | PK |
| project_id | UUID | NO | | FK → projects.id |
| user_id | UUID | NO | | FK → users.id |
| project_role | ENUM | NO | 'member' | 'lead' / 'member' |
| created_at | TIMESTAMP | NO | now() | |

**インデックス**
- UNIQUE (project_id, user_id)
- INDEX (user_id)

---

### tasks

| カラム名 | 型 | NULL | デフォルト | 説明 |
|---|---|---|---|---|
| id | UUID | NO | gen_random_uuid() | PK |
| user_id | UUID | NO | | FK → users.id。タスクの登録者・担当者 |
| project_id | UUID | NO | | FK → projects.id |
| name | VARCHAR(500) | NO | | タスク名 |
| estimated_hours | DECIMAL(4,1) | YES | | 予定時間（例：1.5） |
| status | ENUM | NO | 'todo' | 'todo' / 'in_progress' / 'done' |
| is_private | BOOLEAN | NO | false | 非表示フラグ。trueの場合は本人のみ閲覧可 |
| task_date | DATE | NO | | 対象日（当日の日付で登録） |
| created_at | TIMESTAMP | NO | now() | |
| updated_at | TIMESTAMP | NO | now() | |

**インデックス**
- INDEX (user_id, task_date)
- INDEX (project_id, task_date)

**備考**
- is_private = true のタスクはAPI・画面ともに本人以外へ返却しない
- estimated_hours はNULL許容（AI・チャット連携時に時間未記載の場合）

---

### weekly_reports

週報は**ユーザー × 週**の単位で1件作成される。

| カラム名 | 型 | NULL | デフォルト | 説明 |
|---|---|---|---|---|
| id | UUID | NO | gen_random_uuid() | PK |
| user_id | UUID | NO | | FK → users.id |
| tenant_id | UUID | NO | | FK → tenants.id（検索効率化のための非正規化） |
| week_start_date | DATE | NO | | 対象週の月曜日の日付 |
| ai_summary | TEXT | YES | | AIによる作業サマリ文 |
| feeling | TEXT | YES | | 今週の所感（提出時は必須） |
| questions | TEXT | YES | | 疑問・気になった点 |
| issues | TEXT | YES | | 課題・改善提案 |
| status | ENUM | NO | 'draft' | 'draft' / 'ready' / 'submitted' / 'feedback_received' |
| submitted_at | TIMESTAMP | YES | | 提出日時 |
| created_at | TIMESTAMP | NO | now() | |
| updated_at | TIMESTAMP | NO | now() | |

**インデックス**
- UNIQUE (user_id, week_start_date)
- INDEX (tenant_id, week_start_date, status)
- INDEX (user_id, status)

**ステータス遷移**
```
draft → ready（feeling入力時に自動）→ submitted（提出ボタン）→ feedback_received（上長FB送信時）
```

**備考**
- ai_summary はAI自動生成後に格納。ユーザーが「再生成」した場合は上書き
- week_start_date は常に月曜日。アプリ側で正規化して保存

---

### weekly_report_feedbacks

上長からのフィードバック（コメント）。1週報につき上長1人が1件送れる。

| カラム名 | 型 | NULL | デフォルト | 説明 |
|---|---|---|---|---|
| id | UUID | NO | gen_random_uuid() | PK |
| weekly_report_id | UUID | NO | | FK → weekly_reports.id |
| manager_user_id | UUID | NO | | FK → users.id（フィードバックを送った上長） |
| comment | TEXT | YES | | テキストコメント。リアクションのみの場合はNULL |
| created_at | TIMESTAMP | NO | now() | |
| updated_at | TIMESTAMP | NO | now() | |

**インデックス**
- UNIQUE (weekly_report_id, manager_user_id)
- INDEX (manager_user_id)

---

### weekly_report_reactions

上長フィードバックに紐づくリアクション。1フィードバックにつき同一種別のリアクションは1件まで。

| カラム名 | 型 | NULL | デフォルト | 説明 |
|---|---|---|---|---|
| id | UUID | NO | gen_random_uuid() | PK |
| feedback_id | UUID | NO | | FK → weekly_report_feedbacks.id |
| reaction_type | ENUM | NO | | 'like' / 'star' / 'heart' / 'party' / 'muscle' / 'idea' |
| created_at | TIMESTAMP | NO | now() | |

**インデックス**
- UNIQUE (feedback_id, reaction_type)

**リアクション種別**
| reaction_type | 表示 | 意味 |
|---|---|---|
| like | 👍 | よくできました |
| star | ⭐ | 今週のベスト |
| heart | ❤️ | ありがとう |
| party | 🎉 | おめでとう |
| muscle | 💪 | 引き続き頑張れ |
| idea | 💡 | 参考になりました |

---

## 主要なクエリパターン

### ダッシュボード（当日のプロジェクトメンバー全員のタスク取得）
```sql
SELECT t.*
FROM tasks t
JOIN project_members pm ON pm.user_id = t.user_id
WHERE pm.project_id = :project_id
  AND t.task_date = CURRENT_DATE
  AND (t.user_id = :current_user_id OR t.is_private = false)
ORDER BY t.user_id, t.created_at;
```

### 週報受信トレイ（上長が担当メンバーの週報を一覧取得）
```sql
SELECT wr.*, u.name, u.email
FROM weekly_reports wr
JOIN users u ON u.id = wr.user_id
JOIN tenant_users tu ON tu.user_id = wr.user_id AND tu.tenant_id = :tenant_id
WHERE tu.manager_user_id = :manager_user_id
  AND wr.week_start_date = :week_start_date
ORDER BY wr.submitted_at DESC;
```

### AIサマリ生成用（週次タスク集計）
```sql
SELECT t.name, t.estimated_hours, t.status, p.name AS project_name
FROM tasks t
JOIN projects p ON p.id = t.project_id
WHERE t.user_id = :user_id
  AND t.task_date BETWEEN :week_start AND :week_end
  AND t.is_private = false
ORDER BY t.task_date, t.project_id;
```
