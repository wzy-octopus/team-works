"""
28teamworks MCP Server
Claude Desktop からタスク管理・週報照会を自然言語で操作できるようにする。

使い方:
  1. uv sync でパッケージをインストール
  2. 環境変数を設定:
       TEAMWORKS_EMAIL    : ログインメールアドレス
       TEAMWORKS_PASSWORD : パスワード
       TEAMWORKS_TENANT_ID: テナントID（省略時は最初のテナントを使用）
       TEAMWORKS_API_URL  : APIのベースURL（省略時は http://localhost:8000）
  3. Claude Desktop の設定ファイルに登録:
       {
         "mcpServers": {
           "TeamWorks": {
             "command": "uv",
             "args": ["--directory", "/path/to/28teamworks/backend", "run", "python", "mcp_server.py"],
             "env": {
               "TEAMWORKS_EMAIL": "your@email.com",
               "TEAMWORKS_PASSWORD": "your_password",
               "TEAMWORKS_TENANT_ID": "your-tenant-id"
             }
           }
         }
       }
"""

import os
from datetime import date, timedelta

import httpx
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("TeamWorks")

BASE_URL = os.getenv("TEAMWORKS_API_URL", "http://localhost:8000")

_token: str | None = None
_tenant_id: str | None = None


async def _authenticate() -> None:
    global _token, _tenant_id

    email = os.getenv("TEAMWORKS_EMAIL", "")
    password = os.getenv("TEAMWORKS_PASSWORD", "")
    if not email or not password:
        raise RuntimeError(
            "環境変数 TEAMWORKS_EMAIL と TEAMWORKS_PASSWORD を設定してください。"
        )

    async with httpx.AsyncClient(base_url=BASE_URL) as client:
        resp = await client.post(
            "/api/auth/login",
            json={"email": email, "password": password},
        )
        resp.raise_for_status()
        data = resp.json()

    _token = data["access_token"]

    env_tenant_id = os.getenv("TEAMWORKS_TENANT_ID", "")
    if env_tenant_id:
        _tenant_id = env_tenant_id
    elif data.get("tenants"):
        _tenant_id = data["tenants"][0]["id"]
    else:
        raise RuntimeError("所属テナントが見つかりませんでした。")


def _auth_headers() -> dict[str, str]:
    return {
        "Authorization": f"Bearer {_token}",
        "X-Tenant-ID": _tenant_id or "",
    }


async def _request(method: str, path: str, **kwargs) -> dict | list | None:
    """認証付きでAPIを呼び出す。401 の場合は再認証して1回リトライする。"""
    global _token

    if not _token:
        await _authenticate()

    for attempt in range(2):
        async with httpx.AsyncClient(base_url=BASE_URL, headers=_auth_headers()) as client:
            resp = await client.request(method, path, **kwargs)

        if resp.status_code == 401 and attempt == 0:
            _token = None
            await _authenticate()
            continue

        resp.raise_for_status()
        if resp.status_code == 204:
            return None
        return resp.json()

    return None  # unreachable


def _today() -> str:
    return date.today().isoformat()


def _current_week_start() -> str:
    today = date.today()
    return (today - timedelta(days=today.weekday())).isoformat()


def _format_team_dashboard(data: dict, project_id: str, target_date: str) -> str:
    """ダッシュボード API のレスポンスをチーム一覧テキストに整形する。

    自分のタスクは全件（非公開含む）。他メンバーは公開タスクのみで、非公開は
    private_counts の件数だけを表示する（Web のチームダッシュボードと同じ可視性）。
    """
    tasks = data.get("tasks", []) if isinstance(data, dict) else []
    private_counts = data.get("private_counts", {}) if isinstance(data, dict) else {}
    status_label = {"todo": "未着手", "in_progress": "進行中", "done": "完了"}
    project_name = tasks[0]["project_name"] if tasks else project_id

    by_user: dict[str, dict] = {}
    for t in tasks:
        u = by_user.setdefault(t["user_id"], {"name": t["user_name"], "tasks": []})
        u["tasks"].append(t)

    lines = [f"【チームダッシュボード】{project_name} / {target_date}（タスク {len(tasks)}件）"]
    if not by_user:
        lines.append("（表示できるタスクはありません）")
        return "\n".join(lines)

    for uid, info in by_user.items():
        done = sum(1 for t in info["tasks"] if t["status"] == "done")
        lines.append(f"\n■ {info['name']}（{done}/{len(info['tasks'])} 完了）")
        for t in info["tasks"]:
            hours = f"{t['estimated_hours']}h" if t.get("estimated_hours") else "-"
            lock = " 🔒" if t.get("is_private") else ""
            label = status_label.get(t["status"], t["status"])
            lines.append(f"  - [{label}] {t['name']}（{hours}）{lock}")
        cnt = private_counts.get(uid, 0)
        if cnt:
            lines.append(f"  🔒 非表示 {cnt}件")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# ツール定義
# ---------------------------------------------------------------------------


@mcp.tool()
async def list_tasks(task_date: str | None = None, project_id: str | None = None) -> str:
    """指定日のマイタスク一覧を取得する。

    Args:
        task_date: タスクの日付（YYYY-MM-DD形式。省略時は当日）
        project_id: プロジェクトIDでフィルタ（省略時は全プロジェクト）
    """
    params: dict[str, str] = {}
    if task_date:
        params["task_date"] = task_date
    if project_id:
        params["project_id"] = project_id

    data = await _request("GET", "/api/tasks", params=params)
    tasks = data.get("tasks", []) if isinstance(data, dict) else []
    target_date = task_date or _today()

    if not tasks:
        return f"{target_date} のタスクはありません。"

    status_label = {"todo": "未着手", "in_progress": "進行中", "done": "完了"}
    lines = [f"【{target_date} のタスク一覧】（{len(tasks)}件）"]
    for t in tasks:
        hours = f"{t['estimated_hours']}h" if t["estimated_hours"] else "-"
        lock = " 🔒" if t["is_private"] else ""
        label = status_label.get(t["status"], t["status"])
        lines.append(f"- [{label}] {t['name']}（{hours}）{lock}  ID: {t['id']}")

    return "\n".join(lines)


@mcp.tool()
async def add_task(
    name: str,
    estimated_hours: float | None = None,
    project_id: str | None = None,
    is_private: bool = False,
    task_date: str | None = None,
) -> str:
    """タスクを追加する。

    Args:
        name: タスク名（例: 「要件定義」）
        estimated_hours: 予定時間（例: 1.5）
        project_id: プロジェクトID（list_projects ツールで確認できる）
        is_private: True にするとチームメンバーに非表示になる
        task_date: タスクの日付（YYYY-MM-DD。省略時は当日）
    """
    body = {
        "name": name,
        "estimated_hours": estimated_hours,
        "project_id": project_id,
        "is_private": is_private,
        "task_date": task_date or _today(),
    }
    task = await _request("POST", "/api/tasks", json=body)
    if not task:
        return "タスクの追加に失敗しました。"

    hours = f"{task['estimated_hours']}h" if task["estimated_hours"] else "-"
    lock = " 🔒非表示" if task["is_private"] else ""
    return f"タスクを追加しました ✓\n名前: {task['name']}\n予定時間: {hours}{lock}\nID: {task['id']}"


@mcp.tool()
async def update_task_status(task_id: str, status: str) -> str:
    """タスクのステータスを変更する。

    Args:
        task_id: タスクID（list_tasks ツールで確認できる）
        status: 新しいステータス（"todo" / "in_progress" / "done"）
    """
    valid = ("todo", "in_progress", "done")
    if status not in valid:
        return f"status は {valid} のいずれかを指定してください。"

    task = await _request("PATCH", f"/api/tasks/{task_id}", json={"status": status})
    if not task:
        return "更新に失敗しました。"

    label = {"todo": "未着手", "in_progress": "進行中", "done": "完了"}[status]
    return f"ステータスを更新しました ✓\n{task['name']} → {label}"


@mcp.tool()
async def delete_task(task_id: str) -> str:
    """タスクを削除する。

    Args:
        task_id: タスクID（list_tasks ツールで確認できる）
    """
    await _request("DELETE", f"/api/tasks/{task_id}")
    return f"タスク（ID: {task_id}）を削除しました。"


@mcp.tool()
async def get_weekly_report(week_start_date: str | None = None) -> str:
    """週報を取得する。

    Args:
        week_start_date: 週の開始日（月曜日、YYYY-MM-DD形式。省略時は今週）
    """
    target_week = week_start_date or _current_week_start()

    data = await _request(
        "GET",
        "/api/weekly-reports/current",
        params={"week_start_date": target_week},
    )
    if not isinstance(data, dict):
        return "週報の取得に失敗しました。"

    status_label = {
        "draft": "下書き",
        "ready": "提出可能",
        "submitted": "提出済み",
        "feedback_received": "FB済み",
    }
    status = status_label.get(str(data.get("status")), str(data.get("status")))

    lines = [f"【週報 {target_week}（月）〜】", f"ステータス: {status}"]

    if data.get("ai_summary"):
        lines.append(f"\n■ AIサマリ\n{data['ai_summary']}")
    if data.get("feeling"):
        lines.append(f"\n■ 今週の所感\n{data['feeling']}")
    if data.get("questions"):
        lines.append(f"\n■ 疑問・気になった点\n{data['questions']}")
    if data.get("issues"):
        lines.append(f"\n■ 課題・改善提案\n{data['issues']}")
    if not any([data.get("ai_summary"), data.get("feeling"), data.get("questions"), data.get("issues")]):
        lines.append("\n（まだ内容がありません）")

    return "\n".join(lines)


@mcp.tool()
async def list_projects() -> str:
    """プロジェクト一覧を取得する。add_task の project_id として使用できる。"""
    data = await _request("GET", "/api/admin/projects")
    projects = data if isinstance(data, list) else []

    if not projects:
        return "参加しているプロジェクトはありません。"

    lines = [f"【プロジェクト一覧】（{len(projects)}件）"]
    for p in projects:
        lines.append(f"- {p['name']}  ID: {p['id']}")
    return "\n".join(lines)


@mcp.tool()
async def get_team_dashboard(project_id: str, task_date: str | None = None) -> str:
    """指定プロジェクトのチームダッシュボード（全メンバーのタスク一覧）を取得する。

    自分のタスクは全件、他メンバーは公開タスクのみ（非公開は件数のみ）表示する。
    閲覧権限のあるプロジェクトに限る（所属していない/権限が無ければエラー）。
    project_id は list_projects で確認できる。

    Args:
        project_id: プロジェクトID（必須）
        task_date: 日付（YYYY-MM-DD。省略時は当日）
    """
    target_date = task_date or _today()
    params = {"project_id": project_id, "task_date": target_date}
    data = await _request("GET", "/api/dashboard", params=params)
    if not isinstance(data, dict):
        return "ダッシュボードの取得に失敗しました。"
    return _format_team_dashboard(data, project_id, target_date)


if __name__ == "__main__":
    mcp.run()
