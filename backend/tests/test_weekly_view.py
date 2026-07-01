"""週表示のテスト（/tasks?week_start と /dashboard/week）。

単日エンドポイントと同じアクセス制御・private 規則が週集計でも守られることを重点確認する。
"""

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.models.models import Project, ProjectMember, Task, Tenant, TenantUser, User

WEEK_START = "2026-05-04"  # 月曜想定。days = 05-04 .. 05-10


def _member(payload: dict, user_id: str) -> dict:
    """/dashboard/week 応答から指定ユーザーの members エントリを返す。"""
    return next(m for m in payload["members"] if m["user_id"] == user_id)


def _day(member: dict, date_str: str) -> dict:
    """members エントリから指定日の集計を返す。"""
    return next(d for d in member["days"] if d["date"] == date_str)


# ---------------------------------------------------------------------------
# GET /tasks?week_start=
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_tasks_by_week_returns_only_that_week(alice_client: AsyncClient) -> None:
    """week_start 指定時、その週（月〜日）のタスクだけを返す。"""
    for d in ("2026-05-04", "2026-05-06", "2026-05-10", "2026-05-11"):
        resp = await alice_client.post(
            "/api/tasks", json={"name": f"task {d}", "task_date": d}
        )
        assert resp.status_code == 201

    resp = await alice_client.get(f"/api/tasks?week_start={WEEK_START}")
    assert resp.status_code == 200
    dates = sorted(t["task_date"] for t in resp.json()["tasks"])
    assert dates == ["2026-05-04", "2026-05-06", "2026-05-10"]  # 05-11 は翌週で除外


@pytest.mark.asyncio
async def test_list_tasks_single_day_unchanged(alice_client: AsyncClient) -> None:
    """week_start 未指定なら従来通り単日のみ返す（回帰確認）。"""
    for d in ("2026-05-13", "2026-05-14"):
        await alice_client.post("/api/tasks", json={"name": f"task {d}", "task_date": d})

    resp = await alice_client.get("/api/tasks?task_date=2026-05-13")
    assert resp.status_code == 200
    dates = [t["task_date"] for t in resp.json()["tasks"]]
    assert dates == ["2026-05-13"]


@pytest.mark.asyncio
async def test_list_tasks_week_only_own_tasks(
    alice_client: AsyncClient,
    bob_client: AsyncClient,
) -> None:
    """週表示でも他人のタスクは返さない（本人スコープ）。"""
    await bob_client.post("/api/tasks", json={"name": "bob week task", "task_date": "2026-05-05"})
    await alice_client.post("/api/tasks", json={"name": "alice week task", "task_date": "2026-05-05"})

    resp = await alice_client.get(f"/api/tasks?week_start={WEEK_START}")
    names = [t["name"] for t in resp.json()["tasks"]]
    assert "alice week task" in names
    assert "bob week task" not in names


# ---------------------------------------------------------------------------
# GET /dashboard/week
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_dashboard_week_aggregation(
    alice_client: AsyncClient,
    project_with_members: Project,
    user_alice: tuple[User, TenantUser],
    user_bob: tuple[User, TenantUser],
    db: AsyncSession,
) -> None:
    """メンバー別・日別・status 別の集計が正しく、private の扱いが単日と一致する。"""
    alice, _ = user_alice
    bob, _ = user_bob
    project = project_with_members

    db.add_all(
        [
            # alice 公開: 05-04 todo + done
            Task(user_id=alice.id, project_id=project.id, name="a1", status="todo",
                 is_private=False, task_date="2026-05-04"),
            Task(user_id=alice.id, project_id=project.id, name="a2", status="done",
                 is_private=False, task_date="2026-05-04"),
            # alice 自分の private: 05-06 todo（自分の status 集計に含める）
            Task(user_id=alice.id, project_id=project.id, name="a3", status="todo",
                 is_private=True, task_date="2026-05-06"),
            # bob 公開: 05-04 in_progress / 05-05 done
            Task(user_id=bob.id, project_id=project.id, name="b1", status="in_progress",
                 is_private=False, task_date="2026-05-04"),
            Task(user_id=bob.id, project_id=project.id, name="b2", status="done",
                 is_private=False, task_date="2026-05-05"),
            # bob private: 05-04（件数のみ・詳細は漏らさない）
            Task(user_id=bob.id, project_id=project.id, name="b3secret", status="todo",
                 is_private=True, task_date="2026-05-04"),
        ]
    )
    await db.commit()

    resp = await alice_client.get(
        f"/api/dashboard/week?project_id={project.id}&week_start={WEEK_START}"
    )
    assert resp.status_code == 200
    data = resp.json()

    assert data["week_start"] == WEEK_START
    assert data["days"] == [
        "2026-05-04", "2026-05-05", "2026-05-06",
        "2026-05-07", "2026-05-08", "2026-05-09", "2026-05-10",
    ]

    # alice（自分）: 05-04 todo=1 done=1、05-06 は自分の private を含めて todo=1、private_count=0
    a = _member(data, alice.id)
    assert _day(a, "2026-05-04")["todo"] == 1
    assert _day(a, "2026-05-04")["done"] == 1
    assert _day(a, "2026-05-06")["todo"] == 1
    assert _day(a, "2026-05-06")["private_count"] == 0

    # bob（他人）: 05-04 in_progress=1・private_count=1・todo=0（private は status に入れない）、05-05 done=1
    b = _member(data, bob.id)
    assert _day(b, "2026-05-04")["in_progress"] == 1
    assert _day(b, "2026-05-04")["todo"] == 0
    assert _day(b, "2026-05-04")["private_count"] == 1
    assert _day(b, "2026-05-05")["done"] == 1


@pytest.mark.asyncio
async def test_dashboard_week_task_detail_respects_privacy(
    alice_client: AsyncClient,
    project_with_members: Project,
    user_alice: tuple[User, TenantUser],
    user_bob: tuple[User, TenantUser],
    db: AsyncSession,
) -> None:
    """人名展開用の tasks 明細: 自分の private は含む・他人の public は含む・他人の private は含まない。"""
    alice, _ = user_alice
    bob, _ = user_bob
    db.add_all(
        [
            Task(user_id=alice.id, project_id=project_with_members.id, name="alice-private",
                 status="todo", is_private=True, task_date="2026-05-04"),
            Task(user_id=bob.id, project_id=project_with_members.id, name="bob-public",
                 status="done", is_private=False, task_date="2026-05-05"),
            Task(user_id=bob.id, project_id=project_with_members.id, name="bob-private",
                 status="todo", is_private=True, task_date="2026-05-05"),
        ]
    )
    await db.commit()

    resp = await alice_client.get(
        f"/api/dashboard/week?project_id={project_with_members.id}&week_start={WEEK_START}"
    )
    assert resp.status_code == 200
    names = {t["name"]: t for t in resp.json()["tasks"]}
    assert "alice-private" in names  # 自分の private は明細に含まれる
    assert names["alice-private"]["is_private"] is True
    assert "bob-public" in names  # 他人の公開タスクは含まれる
    assert "bob-private" not in names  # 他人の private は含まれない


@pytest.mark.asyncio
async def test_dashboard_week_does_not_leak_private_names(
    alice_client: AsyncClient,
    project_with_members: Project,
    user_bob: tuple[User, TenantUser],
    db: AsyncSession,
) -> None:
    """週集計応答に他人の private タスク名（詳細）が一切含まれない。"""
    bob, _ = user_bob
    db.add(
        Task(user_id=bob.id, project_id=project_with_members.id, name="b3secret",
             status="todo", is_private=True, task_date="2026-05-04")
    )
    await db.commit()

    resp = await alice_client.get(
        f"/api/dashboard/week?project_id={project_with_members.id}&week_start={WEEK_START}"
    )
    assert resp.status_code == 200
    assert "b3secret" not in resp.text


@pytest.mark.asyncio
async def test_dashboard_week_non_member_forbidden(
    alice_client: AsyncClient,
    project: Project,
    user_bob: tuple[User, TenantUser],
    db: AsyncSession,
) -> None:
    """未所属 project の週集計は member/manager には 403（BUG-024 と同一）。"""
    bob, _ = user_bob
    db.add(ProjectMember(project_id=project.id, user_id=bob.id))  # bob のみメンバー
    await db.commit()

    resp = await alice_client.get(
        f"/api/dashboard/week?project_id={project.id}&week_start={WEEK_START}"
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_dashboard_week_admin_can_view_any_project(
    admin_client: AsyncClient,
    project_with_members: Project,
) -> None:
    """admin は未所属でもテナント内 project の週集計を閲覧できる（200）。"""
    resp = await admin_client.get(
        f"/api/dashboard/week?project_id={project_with_members.id}&week_start={WEEK_START}"
    )
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_dashboard_week_cross_tenant_isolation(
    alice_client: AsyncClient, db: AsyncSession
) -> None:
    """別テナントの project_id を指定しても週集計は漏れない（404）。"""
    other_tenant = Tenant(name=f"Other {uuid.uuid4().hex[:8]}")
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
    other_proj = Project(tenant_id=other_tenant.id, name="Foreign Proj", color="#111111")
    db.add(other_proj)
    await db.flush()
    db.add(ProjectMember(project_id=other_proj.id, user_id=other_user.id))
    await db.commit()

    resp = await alice_client.get(
        f"/api/dashboard/week?project_id={other_proj.id}&week_start={WEEK_START}"
    )
    assert resp.status_code == 404
