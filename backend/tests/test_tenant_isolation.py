"""テナント隔離のテスト（ダッシュボード閲覧・プロジェクトメンバー操作の境界）。"""

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.models.models import Project, ProjectMember, Task, Tenant, TenantUser, User


async def _make_other_tenant_user(db: AsyncSession) -> tuple[Tenant, User]:
    """別テナントとそのメンバーを 1 件作成して返す。"""
    other_tenant = Tenant(name=f"Other Tenant {uuid.uuid4().hex[:8]}")
    db.add(other_tenant)
    await db.flush()
    other_user = User(
        email=f"foreign_{uuid.uuid4().hex[:8]}@example.com",
        name="Foreign",
        hashed_password=hash_password("password123"),
    )
    db.add(other_user)
    await db.flush()
    db.add(TenantUser(tenant_id=other_tenant.id, user_id=other_user.id, role="member"))
    return other_tenant, other_user


@pytest.mark.asyncio
async def test_dashboard_cross_tenant_isolation(
    alice_client: AsyncClient, db: AsyncSession
) -> None:
    """別テナントの project_id を指定しても、そのプロジェクトの公開タスクは漏れない（404）。"""
    other_tenant, other_user = await _make_other_tenant_user(db)
    other_proj = Project(tenant_id=other_tenant.id, name="Foreign Proj", color="#111111")
    db.add(other_proj)
    await db.flush()
    db.add(ProjectMember(project_id=other_proj.id, user_id=other_user.id))
    db.add(
        Task(
            user_id=other_user.id,
            project_id=other_proj.id,
            name="他テナントの公開タスク",
            status="todo",
            is_private=False,
            task_date="2026-05-20",
        )
    )
    await db.commit()

    resp = await alice_client.get(
        f"/api/dashboard?project_id={other_proj.id}&task_date=2026-05-20"
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_add_member_cross_tenant_user_rejected(
    admin_client: AsyncClient, project: Project, db: AsyncSession
) -> None:
    """別テナントのユーザーを自テナントのプロジェクトに追加できない（404）。"""
    _, foreign_user = await _make_other_tenant_user(db)
    await db.commit()

    resp = await admin_client.post(
        f"/api/admin/projects/{project.id}/members?user_id={foreign_user.id}"
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_list_projects_member_sees_only_member_projects(
    alice_client: AsyncClient,
    project_with_members: Project,
    db: AsyncSession,
) -> None:
    """member は /admin/projects で自分が所属する project のみ取得する（BUG-024）。"""
    other = Project(
        tenant_id=project_with_members.tenant_id, name="No Alice Project", color="#000000"
    )
    db.add(other)
    await db.commit()

    resp = await alice_client.get("/api/admin/projects")
    assert resp.status_code == 200
    ids = [p["id"] for p in resp.json()]
    assert project_with_members.id in ids
    assert other.id not in ids


@pytest.mark.asyncio
async def test_list_projects_admin_sees_all(
    admin_client: AsyncClient,
    project_with_members: Project,
    db: AsyncSession,
) -> None:
    """admin は /admin/projects でテナント内の全 project を取得する（未所属でも）。"""
    other = Project(
        tenant_id=project_with_members.tenant_id, name="Admin Sees This", color="#111111"
    )
    db.add(other)
    await db.commit()

    resp = await admin_client.get("/api/admin/projects")
    assert resp.status_code == 200
    ids = [p["id"] for p in resp.json()]
    assert project_with_members.id in ids
    assert other.id in ids


@pytest.mark.asyncio
async def test_remove_member_cross_tenant_project_rejected(
    admin_client: AsyncClient, db: AsyncSession
) -> None:
    """別テナントのプロジェクトのメンバーを除外できない（404）。"""
    other_tenant, other_user = await _make_other_tenant_user(db)
    other_proj = Project(tenant_id=other_tenant.id, name="Foreign Proj 2", color="#222222")
    db.add(other_proj)
    await db.flush()
    db.add(ProjectMember(project_id=other_proj.id, user_id=other_user.id))
    await db.commit()

    resp = await admin_client.delete(
        f"/api/admin/projects/{other_proj.id}/members/{other_user.id}"
    )
    assert resp.status_code == 404
