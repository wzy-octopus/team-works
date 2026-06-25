"""HTTP 版 MCP サーバー（FastAPI の /mcp に mount する）。

stdio 版 (mcp_server.py) と異なり、認証は **呼び出し元の JWT を転送して既存 REST API に
委譲** する。これによりテナント隔離・private ルールを API 側に一元化する（ツール側で
アクセス制御を再実装しない）。

フロー:
  1. ASGI 認証ゲート (authed_mcp_app) が Authorization ヘッダの Bearer JWT を検証。
  2. 有効なら contextvar (_mcp_token) に生トークンを格納して内側 MCP アプリへ委譲。
  3. 各ツールは contextvar からトークンを読み、Authorization ヘッダ付きで内部 API を呼ぶ。

session manager は FastAPI 側の lifespan で `mcp.session_manager.run()` を起動すること。
"""

import contextvars
import os
from datetime import date, timedelta

import httpx
from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings

from app.core.database import AsyncSessionLocal
from app.core.security import resolve_user_context

BASE_URL = os.getenv("INTERNAL_API_URL", "http://127.0.0.1:8000")

# 認証ゲートが格納した呼び出し元 JWT を、同一リクエストの async コンテキスト内でツールが読む。
_mcp_token: contextvars.ContextVar[str] = contextvars.ContextVar("mcp_token", default="")

mcp = FastMCP(
    "TeamWorks",
    # MCP SDK の DNS リバインディング保護は Host を localhost に限定するため、Azure の
    # 公開ドメインだと 421 "Invalid Host header" になる。認証は MCPMiddleware の Bearer JWT
    # で行っており（Cookie 非依存＝ブラウザ経由 DNS リバインディングの脅威が無い）、この
    # 保護は不要なので無効化する。
    transport_security=TransportSecuritySettings(enable_dns_rebinding_protection=False),
)
# 既定の streamable_http_path は "/mcp"。ミドルウェアが元の scope path をそのまま
# 内側アプリへ渡すため、既定のままにする（内側ルートは "/mcp"）。


def _auth_headers() -> dict[str, str]:
    return {"Authorization": f"Bearer {_mcp_token.get()}"}


async def _request(method: str, path: str, **kwargs) -> dict | list | None:
    """認証付き（呼び出し元 JWT 転送）で内部 API を呼ぶ。"""
    async with httpx.AsyncClient(base_url=BASE_URL, headers=_auth_headers()) as client:
        resp = await client.request(method, path, **kwargs)
    resp.raise_for_status()
    if resp.status_code == 204:
        return None
    return resp.json()


def _today() -> str:
    return date.today().isoformat()


def _current_week_start() -> str:
    today = date.today()
    return (today - timedelta(days=today.weekday())).isoformat()


# ---------------------------------------------------------------------------
# ツール定義（stdio 版 mcp_server.py と同一の振る舞い）
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


# ---------------------------------------------------------------------------
# ASGI 認証ミドルウェア
#   /mcp 配下を Starlette ルーティングより前段で横取りし、Bearer JWT を検証 →
#   contextvar に格納 → 内側 MCP アプリへ委譲する。
#   （Mount だと redirect_slashes=False のとき bare "/mcp" がマッチしないため、
#    プレフィックス判定を自前で行う pure ASGI ミドルウェアにする。）
# ---------------------------------------------------------------------------

_inner_app = mcp.streamable_http_app()


def _is_mcp_path(path: str) -> bool:
    return path == "/mcp" or path.startswith("/mcp/")


class MCPMiddleware:
    """/mcp 配下を認証して内側 MCP アプリへ委譲する pure ASGI ミドルウェア。"""

    def __init__(self, app) -> None:
        self.app = app

    async def __call__(self, scope, receive, send) -> None:
        if scope["type"] != "http" or not _is_mcp_path(scope.get("path", "")):
            await self.app(scope, receive, send)
            return

        headers = dict(scope.get("headers") or [])
        raw = headers.get(b"authorization", b"").decode()
        token = raw[7:] if raw[:7].lower() == "bearer " else ""

        ctx = None
        if token:
            async with AsyncSessionLocal() as db:
                ctx = await resolve_user_context(token, db)

        if not ctx:
            await send(
                {
                    "type": "http.response.start",
                    "status": 401,
                    "headers": [(b"content-type", b"application/json")],
                }
            )
            await send({"type": "http.response.body", "body": b'{"detail":"Unauthorized"}'})
            return

        reset = _mcp_token.set(token)
        try:
            await _inner_app(scope, receive, send)
        finally:
            _mcp_token.reset(reset)
