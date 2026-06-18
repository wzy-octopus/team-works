"""MCP サーバーのツール関数テスト。

ユニットテスト: _request をモックして各ツールの出力・呼び出し引数を検証する。
統合テスト: FastAPI テストアプリに対して実際にHTTP呼び出しを行い、エンドツーエンドで検証する。
"""

import sys
from pathlib import Path

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from unittest.mock import AsyncMock, patch

# backend/ ディレクトリを path に追加して mcp_server をインポート
sys.path.insert(0, str(Path(__file__).parent.parent))

import mcp_server
from app.main import app
from app.models.models import Project, Tenant, TenantUser, User
from tests.conftest import make_token


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def reset_mcp_auth():
    """各テスト前後で MCP サーバーの認証グローバル状態をリセットする。"""
    original_token = mcp_server._token
    original_tenant = mcp_server._tenant_id
    mcp_server._token = "test-token"
    mcp_server._tenant_id = "test-tenant-id"
    yield
    mcp_server._token = original_token
    mcp_server._tenant_id = original_tenant


@pytest_asyncio.fixture
async def mcp_client(
    user_alice: tuple[User, TenantUser],
    tenant: Tenant,
) -> AsyncClient:
    """mcp_server の _request が FastAPI テストアプリに接続するよう設定する。"""
    alice, _ = user_alice
    token = make_token(alice, tenant)
    mcp_server._token = token
    mcp_server._tenant_id = tenant.id
    mcp_server.BASE_URL = "http://test"

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        headers={
            "Authorization": f"Bearer {token}",
            "X-Tenant-ID": tenant.id,
        },
    ) as client:
        yield client


# ---------------------------------------------------------------------------
# list_tasks - ユニットテスト
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_tasks_empty():
    with patch("mcp_server._request", new=AsyncMock(return_value={"tasks": []})):
        result = await mcp_server.list_tasks()
    assert "タスクはありません" in result


@pytest.mark.asyncio
async def test_list_tasks_returns_formatted_output():
    mock_data = {
        "tasks": [
            {"id": "t1", "name": "要件定義", "estimated_hours": 2.0,
             "status": "todo", "is_private": False},
            {"id": "t2", "name": "秘密の作業", "estimated_hours": None,
             "status": "in_progress", "is_private": True},
            {"id": "t3", "name": "コードレビュー", "estimated_hours": 1.5,
             "status": "done", "is_private": False},
        ]
    }
    with patch("mcp_server._request", new=AsyncMock(return_value=mock_data)):
        result = await mcp_server.list_tasks(task_date="2026-06-16")

    assert "2026-06-16" in result
    assert "3件" in result
    assert "未着手" in result
    assert "進行中" in result
    assert "完了" in result
    assert "🔒" in result
    assert "2.0h" in result
    assert "-" in result   # estimated_hours が None の場合
    assert "t1" in result


@pytest.mark.asyncio
async def test_list_tasks_calls_correct_endpoint():
    mock_req = AsyncMock(return_value={"tasks": []})
    with patch("mcp_server._request", new=mock_req):
        await mcp_server.list_tasks(task_date="2026-06-16", project_id="proj-1")
    mock_req.assert_called_once_with(
        "GET", "/api/tasks",
        params={"task_date": "2026-06-16", "project_id": "proj-1"},
    )


@pytest.mark.asyncio
async def test_list_tasks_omits_params_when_none():
    mock_req = AsyncMock(return_value={"tasks": []})
    with patch("mcp_server._request", new=mock_req):
        await mcp_server.list_tasks()
    # project_id が None の場合は params に含めない
    called_params = mock_req.call_args.kwargs.get("params", {})
    assert "project_id" not in called_params


@pytest.mark.asyncio
async def test_list_tasks_handles_none_response():
    """_request が None を返しても AttributeError にならないこと。"""
    with patch("mcp_server._request", new=AsyncMock(return_value=None)):
        result = await mcp_server.list_tasks()
    assert "タスクはありません" in result


# ---------------------------------------------------------------------------
# add_task - ユニットテスト
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_add_task_success():
    mock_data = {
        "id": "new-task-id", "name": "新規タスク",
        "estimated_hours": 1.5, "status": "todo",
        "is_private": False, "task_date": "2026-06-16",
        "project_id": None, "user_id": "u1",
        "created_at": "2026-06-16T00:00:00",
    }
    with patch("mcp_server._request", new=AsyncMock(return_value=mock_data)):
        result = await mcp_server.add_task("新規タスク", estimated_hours=1.5)

    assert "新規タスク" in result
    assert "1.5h" in result
    assert "new-task-id" in result
    assert "✓" in result


@pytest.mark.asyncio
async def test_add_task_private_shows_lock():
    mock_data = {
        "id": "private-id", "name": "秘密のタスク",
        "estimated_hours": None, "status": "todo",
        "is_private": True, "task_date": "2026-06-16",
        "project_id": None, "user_id": "u1",
        "created_at": "2026-06-16T00:00:00",
    }
    with patch("mcp_server._request", new=AsyncMock(return_value=mock_data)):
        result = await mcp_server.add_task("秘密のタスク", is_private=True)

    assert "🔒非表示" in result


@pytest.mark.asyncio
async def test_add_task_no_hours_shows_dash():
    mock_data = {
        "id": "t1", "name": "タスク", "estimated_hours": None,
        "status": "todo", "is_private": False, "task_date": "2026-06-16",
        "project_id": None, "user_id": "u1", "created_at": "2026-06-16T00:00:00",
    }
    with patch("mcp_server._request", new=AsyncMock(return_value=mock_data)):
        result = await mcp_server.add_task("タスク")

    assert "-" in result


@pytest.mark.asyncio
async def test_add_task_sends_correct_body():
    mock_req = AsyncMock(return_value={
        "id": "t1", "name": "テスト", "estimated_hours": 2.0,
        "status": "todo", "is_private": False, "task_date": "2026-06-16",
        "project_id": "p1", "user_id": "u1", "created_at": "2026-06-16T00:00:00",
    })
    with patch("mcp_server._request", new=mock_req):
        await mcp_server.add_task(
            "テスト",
            estimated_hours=2.0,
            project_id="p1",
            task_date="2026-06-16",
        )

    mock_req.assert_called_once_with(
        "POST", "/api/tasks",
        json={
            "name": "テスト",
            "estimated_hours": 2.0,
            "project_id": "p1",
            "is_private": False,
            "task_date": "2026-06-16",
        },
    )


# ---------------------------------------------------------------------------
# update_task_status - ユニットテスト
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_update_task_status_todo():
    mock_data = {
        "id": "t1", "name": "要件定義", "status": "todo",
        "estimated_hours": 2.0, "is_private": False, "task_date": "2026-06-16",
        "project_id": None, "user_id": "u1", "created_at": "2026-06-16T00:00:00",
    }
    with patch("mcp_server._request", new=AsyncMock(return_value=mock_data)):
        result = await mcp_server.update_task_status("t1", "todo")
    assert "未着手" in result
    assert "✓" in result


@pytest.mark.asyncio
async def test_update_task_status_in_progress():
    mock_data = {
        "id": "t1", "name": "コーディング", "status": "in_progress",
        "estimated_hours": 3.0, "is_private": False, "task_date": "2026-06-16",
        "project_id": None, "user_id": "u1", "created_at": "2026-06-16T00:00:00",
    }
    mock_req = AsyncMock(return_value=mock_data)
    with patch("mcp_server._request", new=mock_req):
        result = await mcp_server.update_task_status("t1", "in_progress")

    assert "進行中" in result
    mock_req.assert_called_once_with("PATCH", "/api/tasks/t1", json={"status": "in_progress"})


@pytest.mark.asyncio
async def test_update_task_status_done():
    mock_data = {
        "id": "t1", "name": "テスト", "status": "done",
        "estimated_hours": 1.0, "is_private": False, "task_date": "2026-06-16",
        "project_id": None, "user_id": "u1", "created_at": "2026-06-16T00:00:00",
    }
    with patch("mcp_server._request", new=AsyncMock(return_value=mock_data)):
        result = await mcp_server.update_task_status("t1", "done")
    assert "完了" in result


@pytest.mark.asyncio
async def test_update_task_status_invalid_returns_guidance():
    """無効なステータスを指定したときに _request を呼ばずにガイダンスを返すこと。"""
    mock_req = AsyncMock()
    with patch("mcp_server._request", new=mock_req):
        result = await mcp_server.update_task_status("t1", "finished")

    mock_req.assert_not_called()
    assert "todo" in result
    assert "in_progress" in result
    assert "done" in result


# ---------------------------------------------------------------------------
# delete_task - ユニットテスト
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_delete_task_success():
    with patch("mcp_server._request", new=AsyncMock(return_value=None)):
        result = await mcp_server.delete_task("task-to-delete")

    assert "task-to-delete" in result
    assert "削除" in result


@pytest.mark.asyncio
async def test_delete_task_calls_correct_endpoint():
    mock_req = AsyncMock(return_value=None)
    with patch("mcp_server._request", new=mock_req):
        await mcp_server.delete_task("abc-123")

    mock_req.assert_called_once_with("DELETE", "/api/tasks/abc-123")


# ---------------------------------------------------------------------------
# get_weekly_report - ユニットテスト
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_weekly_report_empty_draft():
    mock_data = {
        "id": "wr1", "user_id": "u1", "week_start_date": "2026-06-15",
        "ai_summary": None, "feeling": None, "questions": None, "issues": None,
        "status": "draft", "submitted_at": None, "created_at": "2026-06-15T00:00:00",
    }
    with patch("mcp_server._request", new=AsyncMock(return_value=mock_data)):
        result = await mcp_server.get_weekly_report("2026-06-15")

    assert "下書き" in result
    assert "まだ内容がありません" in result


@pytest.mark.asyncio
async def test_get_weekly_report_with_full_content():
    mock_data = {
        "id": "wr1", "user_id": "u1", "week_start_date": "2026-06-15",
        "ai_summary": "今週はAPIの実装を完了しました。",
        "feeling": "充実した一週間でした。",
        "questions": "テストの書き方について疑問があります。",
        "issues": "デプロイフローの改善が必要です。",
        "status": "submitted",
        "submitted_at": "2026-06-20T10:00:00",
        "created_at": "2026-06-15T00:00:00",
    }
    with patch("mcp_server._request", new=AsyncMock(return_value=mock_data)):
        result = await mcp_server.get_weekly_report("2026-06-15")

    assert "提出済み" in result
    assert "AIサマリ" in result
    assert "今週はAPIの実装を完了しました。" in result
    assert "今週の所感" in result
    assert "充実した一週間でした。" in result
    assert "疑問・気になった点" in result
    assert "テストの書き方について疑問があります。" in result
    assert "課題・改善提案" in result
    assert "デプロイフローの改善が必要です。" in result


@pytest.mark.asyncio
async def test_get_weekly_report_status_labels():
    for status, expected_label in [
        ("draft", "下書き"),
        ("ready", "提出可能"),
        ("submitted", "提出済み"),
        ("feedback_received", "FB済み"),
    ]:
        mock_data = {
            "id": "wr1", "user_id": "u1", "week_start_date": "2026-06-15",
            "ai_summary": None, "feeling": None, "questions": None, "issues": None,
            "status": status, "submitted_at": None, "created_at": "2026-06-15T00:00:00",
        }
        with patch("mcp_server._request", new=AsyncMock(return_value=mock_data)):
            result = await mcp_server.get_weekly_report("2026-06-15")
        assert expected_label in result, f"status={status} のとき '{expected_label}' が含まれるべき"


@pytest.mark.asyncio
async def test_get_weekly_report_calls_correct_endpoint():
    mock_req = AsyncMock(return_value={
        "id": "wr1", "user_id": "u1", "week_start_date": "2026-06-15",
        "ai_summary": None, "feeling": None, "questions": None, "issues": None,
        "status": "draft", "submitted_at": None, "created_at": "2026-06-15T00:00:00",
    })
    with patch("mcp_server._request", new=mock_req):
        await mcp_server.get_weekly_report("2026-06-15")

    mock_req.assert_called_once_with(
        "GET", "/api/weekly-reports/current",
        params={"week_start_date": "2026-06-15"},
    )


@pytest.mark.asyncio
async def test_get_weekly_report_none_response():
    """_request が None を返したとき失敗メッセージを返すこと。"""
    with patch("mcp_server._request", new=AsyncMock(return_value=None)):
        result = await mcp_server.get_weekly_report("2026-06-15")
    assert "失敗" in result


# ---------------------------------------------------------------------------
# list_projects - ユニットテスト
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_projects_empty():
    with patch("mcp_server._request", new=AsyncMock(return_value=[])):
        result = await mcp_server.list_projects()
    assert "プロジェクトはありません" in result


@pytest.mark.asyncio
async def test_list_projects_returns_formatted_output():
    mock_data = [
        {"id": "p1", "name": "プロジェクトA", "color": "#6366f1",
         "description": None, "member_count": 3},
        {"id": "p2", "name": "プロジェクトB", "color": "#f43f5e",
         "description": "テスト", "member_count": 2},
    ]
    with patch("mcp_server._request", new=AsyncMock(return_value=mock_data)):
        result = await mcp_server.list_projects()

    assert "2件" in result
    assert "プロジェクトA" in result
    assert "プロジェクトB" in result
    assert "p1" in result
    assert "p2" in result


@pytest.mark.asyncio
async def test_list_projects_calls_correct_endpoint():
    mock_req = AsyncMock(return_value=[])
    with patch("mcp_server._request", new=mock_req):
        await mcp_server.list_projects()

    mock_req.assert_called_once_with("GET", "/api/admin/projects")


# ---------------------------------------------------------------------------
# 統合テスト: FastAPI テストアプリに対してエンドツーエンドで検証
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_integration_add_and_list_tasks(
    user_alice: tuple[User, TenantUser],
    tenant: Tenant,
    project: Project,
):
    """add_task → list_tasks の E2E フローを統合テストで検証する。"""
    alice, _ = user_alice
    token = make_token(alice, tenant)
    mcp_server._token = token
    mcp_server._tenant_id = tenant.id

    original_base = mcp_server.BASE_URL
    mcp_server.BASE_URL = "http://test"

    try:
        async def patched_request(method, path, **kwargs):
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test",
                headers={
                    "Authorization": f"Bearer {token}",
                    "X-Tenant-ID": tenant.id,
                },
            ) as client:
                resp = await client.request(method, path, **kwargs)
                if resp.status_code == 204:
                    return None
                return resp.json()

        with patch("mcp_server._request", new=patched_request):
            # タスク追加
            add_result = await mcp_server.add_task(
                "統合テストタスク",
                estimated_hours=2.0,
                task_date="2026-06-16",
            )
            assert "統合テストタスク" in add_result
            assert "2.0h" in add_result
            assert "✓" in add_result

            # タスク一覧に反映されているか
            list_result = await mcp_server.list_tasks(task_date="2026-06-16")
            assert "統合テストタスク" in list_result
    finally:
        mcp_server.BASE_URL = original_base


@pytest.mark.asyncio
async def test_integration_update_and_delete_task(
    user_alice: tuple[User, TenantUser],
    tenant: Tenant,
):
    """add_task → update_task_status → delete_task の E2E フローを検証する。"""
    alice, _ = user_alice
    token = make_token(alice, tenant)
    mcp_server._token = token
    mcp_server._tenant_id = tenant.id

    original_base = mcp_server.BASE_URL
    mcp_server.BASE_URL = "http://test"

    try:
        async def patched_request(method, path, **kwargs):
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test",
                headers={
                    "Authorization": f"Bearer {token}",
                    "X-Tenant-ID": tenant.id,
                },
            ) as client:
                resp = await client.request(method, path, **kwargs)
                if resp.status_code == 204:
                    return None
                return resp.json()

        with patch("mcp_server._request", new=patched_request):
            # タスク追加
            add_result = await mcp_server.add_task("削除予定タスク", task_date="2026-06-17")
            assert "✓" in add_result
            # ID を抽出
            task_id = add_result.split("ID: ")[-1].strip()

            # ステータス更新
            update_result = await mcp_server.update_task_status(task_id, "done")
            assert "完了" in update_result

            # 削除
            delete_result = await mcp_server.delete_task(task_id)
            assert "削除" in delete_result

            # 削除後はリストに出ない
            list_result = await mcp_server.list_tasks(task_date="2026-06-17")
            assert "削除予定タスク" not in list_result
    finally:
        mcp_server.BASE_URL = original_base


@pytest.mark.asyncio
async def test_integration_get_weekly_report(
    user_alice: tuple[User, TenantUser],
    tenant: Tenant,
):
    """get_weekly_report が週報を正しく取得・フォーマットすることを統合テストで検証する。"""
    alice, _ = user_alice
    token = make_token(alice, tenant)
    mcp_server._token = token
    mcp_server._tenant_id = tenant.id

    original_base = mcp_server.BASE_URL
    mcp_server.BASE_URL = "http://test"

    try:
        async def patched_request(method, path, **kwargs):
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test",
                headers={
                    "Authorization": f"Bearer {token}",
                    "X-Tenant-ID": tenant.id,
                },
            ) as client:
                resp = await client.request(method, path, **kwargs)
                if resp.status_code == 204:
                    return None
                return resp.json()

        with patch("mcp_server._request", new=patched_request):
            result = await mcp_server.get_weekly_report("2026-06-15")
            # 新規作成された場合は下書きになる
            assert "2026-06-15" in result
            assert "下書き" in result
    finally:
        mcp_server.BASE_URL = original_base


@pytest.mark.asyncio
async def test_integration_list_projects(
    user_alice: tuple[User, TenantUser],
    tenant: Tenant,
    project_with_members: Project,
):
    """list_projects がプロジェクト一覧を返すことを統合テストで検証する（alice は所属メンバー）。"""
    alice, _ = user_alice
    token = make_token(alice, tenant)
    mcp_server._token = token
    mcp_server._tenant_id = tenant.id

    original_base = mcp_server.BASE_URL
    mcp_server.BASE_URL = "http://test"

    try:
        async def patched_request(method, path, **kwargs):
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test",
                headers={
                    "Authorization": f"Bearer {token}",
                    "X-Tenant-ID": tenant.id,
                },
            ) as client:
                resp = await client.request(method, path, **kwargs)
                if resp.status_code == 204:
                    return None
                return resp.json()

        with patch("mcp_server._request", new=patched_request):
            result = await mcp_server.list_projects()
            # fixture で作られた "Test Project" が含まれる
            assert "Test Project" in result
            assert project_with_members.id in result
    finally:
        mcp_server.BASE_URL = original_base
