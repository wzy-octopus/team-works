"""タスク関連のテスト。"""

from datetime import date, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dates import business_today
from app.models.models import Project, ProjectMember, Task, Tenant, TenantUser, User


# ---------------------------------------------------------------------------
# タスク作成の正常系
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_task_success(
    alice_client: AsyncClient,
    project_with_members: Project,
) -> None:
    """タスクを正常に作成できることを確認する。"""
    payload = {
        "name": "テストタスク",
        "estimated_hours": 2.0,
        "project_id": project_with_members.id,
        "is_private": False,
        "task_date": "2026-05-01",
    }
    response = await alice_client.post("/api/tasks", json=payload)
    assert response.status_code == 201

    data = response.json()
    assert data["name"] == "テストタスク"
    assert data["estimated_hours"] == 2.0
    assert data["project_id"] == project_with_members.id
    assert data["is_private"] is False
    assert data["status"] == "todo"
    assert data["task_date"] == "2026-05-01"
    assert "id" in data
    assert "created_at" in data


@pytest.mark.asyncio
async def test_create_task_without_project(alice_client: AsyncClient) -> None:
    """プロジェクト未指定でタスクを作成できることを確認する。"""
    payload = {
        "name": "プロジェクトなしタスク",
        "task_date": "2026-05-01",
    }
    response = await alice_client.post("/api/tasks", json=payload)
    assert response.status_code == 201

    data = response.json()
    assert data["name"] == "プロジェクトなしタスク"
    assert data["project_id"] is None
    assert data["status"] == "todo"


@pytest.mark.asyncio
async def test_create_private_task(
    alice_client: AsyncClient, project_with_members: Project
) -> None:
    """プライベートタスクを作成できることを確認する。"""
    payload = {
        "name": "秘密のタスク",
        "is_private": True,
        "project_id": project_with_members.id,
        "task_date": "2026-05-01",
    }
    response = await alice_client.post("/api/tasks", json=payload)
    assert response.status_code == 201
    assert response.json()["is_private"] is True


# ---------------------------------------------------------------------------
# BUG-021: プロジェクトメンバーシップ検証（未所属プロジェクトへの作成を禁止）
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_task_in_unassigned_project_forbidden(
    alice_client: AsyncClient, project: Project
) -> None:
    """所属していないプロジェクトにはタスクを作成できない（403）。"""
    payload = {
        "name": "未所属プロジェクトのタスク",
        "project_id": project.id,
        "task_date": "2026-05-08",
    }
    resp = await alice_client.post("/api/tasks", json=payload)
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_create_task_in_member_project_succeeds(
    alice_client: AsyncClient, project_with_members: Project
) -> None:
    """所属プロジェクトにはタスクを作成できる（201）。"""
    payload = {
        "name": "所属プロジェクトのタスク",
        "project_id": project_with_members.id,
        "task_date": "2026-05-08",
    }
    resp = await alice_client.post("/api/tasks", json=payload)
    assert resp.status_code == 201


@pytest.mark.asyncio
async def test_create_task_other_tenant_project_not_found(
    alice_client: AsyncClient, db: AsyncSession
) -> None:
    """別テナントのプロジェクトには作成できない（404・テナント隔離）。"""
    other_tenant = Tenant(name="Other Tenant")
    db.add(other_tenant)
    await db.flush()
    other_proj = Project(tenant_id=other_tenant.id, name="Other Proj", color="#000000")
    db.add(other_proj)
    await db.commit()

    payload = {
        "name": "他テナントのタスク",
        "project_id": other_proj.id,
        "task_date": "2026-05-09",
    }
    resp = await alice_client.post("/api/tasks", json=payload)
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# is_private=true のタスクが他ユーザーのダッシュボードに出ないことの確認
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_private_task_hidden_from_dashboard(
    alice_client: AsyncClient,
    bob_client: AsyncClient,
    project_with_members: Project,
    user_alice: tuple[User, TenantUser],
    user_bob: tuple[User, TenantUser],
) -> None:
    """Aliceのプライベートタスクが、Bobのダッシュボードに表示されないことを確認する。"""
    project = project_with_members
    task_date = "2026-05-02"

    # Alice がプライベートタスクを作成
    private_payload = {
        "name": "Aliceの秘密タスク",
        "is_private": True,
        "project_id": project.id,
        "task_date": task_date,
    }
    create_resp = await alice_client.post("/api/tasks", json=private_payload)
    assert create_resp.status_code == 201

    # Alice が公開タスクも作成
    public_payload = {
        "name": "Aliceの公開タスク",
        "is_private": False,
        "project_id": project.id,
        "task_date": task_date,
    }
    create_resp2 = await alice_client.post("/api/tasks", json=public_payload)
    assert create_resp2.status_code == 201

    # Bob がダッシュボードを取得
    dash_resp = await bob_client.get(
        f"/api/dashboard?project_id={project.id}&task_date={task_date}"
    )
    assert dash_resp.status_code == 200

    dash_data = dash_resp.json()
    alice_user, _ = user_alice

    # Bob 視点: tasks リストから Alice のタスクを抽出
    alice_visible_tasks = [t for t in dash_data["tasks"] if t["user_id"] == alice_user.id]

    # Alice の公開タスクは見える
    assert any(t["name"] == "Aliceの公開タスク" for t in alice_visible_tasks), \
        "公開タスクが表示されるべき"

    # プライベートタスクは tasks リストに含まれない
    assert not any(t["name"] == "Aliceの秘密タスク" for t in alice_visible_tasks), \
        "プライベートタスクは tasks リストに含まれてはいけない"

    # プライベートタスクは private_counts に集計されている
    private_count = dash_data["private_counts"].get(alice_user.id, 0)
    assert private_count >= 1, \
        "プライベートタスクはカウントとして集計されるべき"


@pytest.mark.asyncio
async def test_own_private_task_visible_in_my_tasks(
    alice_client: AsyncClient, project_with_members: Project
) -> None:
    """自分のプライベートタスクは自分のタスク一覧に表示されることを確認する。"""
    task_date = "2026-05-03"
    payload = {
        "name": "私だけ見える",
        "is_private": True,
        "project_id": project_with_members.id,
        "task_date": task_date,
    }
    await alice_client.post("/api/tasks", json=payload)

    resp = await alice_client.get(f"/api/tasks?task_date={task_date}")
    assert resp.status_code == 200

    tasks = resp.json()["tasks"]
    assert any(t["name"] == "私だけ見える" for t in tasks), \
        "本人には自分のプライベートタスクが見えるべき"


# ---------------------------------------------------------------------------
# ステータスサイクル (todo → in_progress → done) の確認
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_task_status_cycle(
    alice_client: AsyncClient, project_with_members: Project
) -> None:
    """タスクのステータスが todo → in_progress → done と遷移できることを確認する。"""
    # タスク作成（デフォルト: todo）
    create_resp = await alice_client.post(
        "/api/tasks",
        json={
            "name": "ステータステスト",
            "task_date": "2026-05-04",
            "project_id": project_with_members.id,
        },
    )
    assert create_resp.status_code == 201
    task_id = create_resp.json()["id"]
    assert create_resp.json()["status"] == "todo"

    # todo → in_progress
    patch_resp = await alice_client.patch(
        f"/api/tasks/{task_id}", json={"status": "in_progress"}
    )
    assert patch_resp.status_code == 200
    assert patch_resp.json()["status"] == "in_progress"

    # in_progress → done
    patch_resp2 = await alice_client.patch(
        f"/api/tasks/{task_id}", json={"status": "done"}
    )
    assert patch_resp2.status_code == 200
    assert patch_resp2.json()["status"] == "done"


@pytest.mark.asyncio
async def test_task_update_name_and_hours(alice_client: AsyncClient) -> None:
    """タスク名と見積時間を更新できることを確認する。"""
    create_resp = await alice_client.post(
        "/api/tasks",
        json={"name": "元の名前", "estimated_hours": 1.0, "task_date": "2026-05-05"},
    )
    assert create_resp.status_code == 201
    task_id = create_resp.json()["id"]

    patch_resp = await alice_client.patch(
        f"/api/tasks/{task_id}",
        json={"name": "変更後の名前", "estimated_hours": 3.5},
    )
    assert patch_resp.status_code == 200
    assert patch_resp.json()["name"] == "変更後の名前"
    assert patch_resp.json()["estimated_hours"] == 3.5


@pytest.mark.asyncio
async def test_delete_task(alice_client: AsyncClient) -> None:
    """タスクを削除できることを確認する。"""
    create_resp = await alice_client.post(
        "/api/tasks",
        json={"name": "削除対象", "task_date": "2026-05-06"},
    )
    task_id = create_resp.json()["id"]

    delete_resp = await alice_client.delete(f"/api/tasks/{task_id}")
    assert delete_resp.status_code == 204

    # 削除後は取得できないことを確認
    list_resp = await alice_client.get("/api/tasks?task_date=2026-05-06")
    tasks = list_resp.json()["tasks"]
    assert not any(t["id"] == task_id for t in tasks)


@pytest.mark.asyncio
async def test_cannot_update_others_task(
    alice_client: AsyncClient,
    bob_client: AsyncClient,
    project: Project,
) -> None:
    """他ユーザーのタスクは更新できないことを確認する。"""
    # Alice がタスク作成
    create_resp = await alice_client.post(
        "/api/tasks",
        json={"name": "Aliceのタスク", "task_date": "2026-05-07"},
    )
    task_id = create_resp.json()["id"]

    # Bob が Alice のタスクを更新しようとする → 404
    patch_resp = await bob_client.patch(
        f"/api/tasks/{task_id}", json={"status": "done"}
    )
    assert patch_resp.status_code == 404


# ---------------------------------------------------------------------------
# BUG-024: ダッシュボードの閲覧権限（未所属 project は member/manager 不可・admin は可）
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_dashboard_non_member_forbidden(
    alice_client: AsyncClient,
    project: Project,
    user_bob: tuple[User, TenantUser],
    db: AsyncSession,
) -> None:
    """member は同一テナントでも未所属 project の dashboard を閲覧できない（403）。"""
    bob, _ = user_bob
    db.add(ProjectMember(project_id=project.id, user_id=bob.id))  # bob のみメンバー
    await db.commit()

    resp = await alice_client.get(f"/api/dashboard?project_id={project.id}")
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_dashboard_admin_can_view_any_project(
    admin_client: AsyncClient,
    project_with_members: Project,
) -> None:
    """admin は自分が未所属でもテナント内 project の dashboard を閲覧できる（200）。"""
    resp = await admin_client.get(f"/api/dashboard?project_id={project_with_members.id}")
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_dashboard_returns_past_incomplete_summary(
    alice_client: AsyncClient,
    project_with_members: Project,
    user_alice: tuple[User, TenantUser],
    user_bob: tuple[User, TenantUser],
    db: AsyncSession,
) -> None:
    """Dashboard returns the previous 30 days of incomplete task counts."""
    alice, _ = user_alice
    bob, _ = user_bob
    today = date.fromisoformat(business_today())
    yesterday = today - timedelta(days=1)
    two_days_ago = today - timedelta(days=2)
    three_days_ago = today - timedelta(days=3)
    thirty_days_ago = today - timedelta(days=30)
    thirty_one_days_ago = today - timedelta(days=31)

    db.add_all(
        [
            Task(
                user_id=alice.id,
                project_id=project_with_members.id,
                name="Alice private unfinished",
                status="todo",
                is_private=True,
                task_date=yesterday.isoformat(),
            ),
            Task(
                user_id=bob.id,
                project_id=project_with_members.id,
                name="Bob public unfinished",
                status="todo",
                is_private=False,
                task_date=yesterday.isoformat(),
            ),
            Task(
                user_id=bob.id,
                project_id=project_with_members.id,
                name="Bob done",
                status="done",
                is_private=False,
                task_date=yesterday.isoformat(),
            ),
            Task(
                user_id=bob.id,
                project_id=project_with_members.id,
                name="Bob private hidden unfinished",
                status="todo",
                is_private=True,
                task_date=yesterday.isoformat(),
            ),
            Task(
                user_id=alice.id,
                project_id=project_with_members.id,
                name="Alice in progress",
                status="in_progress",
                is_private=False,
                task_date=two_days_ago.isoformat(),
            ),
            Task(
                user_id=alice.id,
                project_id=project_with_members.id,
                name="Today unfinished excluded",
                status="todo",
                is_private=False,
                task_date=today.isoformat(),
            ),
            Task(
                user_id=alice.id,
                project_id=project_with_members.id,
                name="Old unfinished excluded",
                status="todo",
                is_private=False,
                task_date=thirty_one_days_ago.isoformat(),
            ),
        ]
    )
    await db.commit()

    resp = await alice_client.get(
        f"/api/dashboard?project_id={project_with_members.id}"
    )
    assert resp.status_code == 200

    summary = resp.json()["past_incomplete_summary"]
    assert summary["total"] == 3
    assert len(summary["items"]) == 30
    assert summary["items"][0] == {
        "task_date": yesterday.isoformat(),
        "count": 2,
    }
    assert summary["items"][1] == {
        "task_date": two_days_ago.isoformat(),
        "count": 1,
    }
    assert summary["items"][2] == {
        "task_date": three_days_ago.isoformat(),
        "count": 0,
    }
    assert summary["items"][-1] == {
        "task_date": thirty_days_ago.isoformat(),
        "count": 0,
    }
