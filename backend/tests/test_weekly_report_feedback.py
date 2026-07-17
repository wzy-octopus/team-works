"""週報フィードバックの未読バッジ関連エンドポイントのテスト。"""

import uuid
from datetime import datetime, timezone

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.models.models import Tenant, TenantUser, User, WeeklyReport, WeeklyReportFeedback


async def _make_manager(db: AsyncSession, tenant: Tenant) -> User:
    manager = User(
        email=f"mgr_{uuid.uuid4().hex[:8]}@example.com",
        name="Manager",
        hashed_password=hash_password("password123"),
    )
    db.add(manager)
    await db.flush()
    db.add(TenantUser(tenant_id=tenant.id, user_id=manager.id, role="manager"))
    return manager


@pytest.mark.asyncio
async def test_unread_count_reflects_new_feedback(
    alice_client: AsyncClient,
    user_alice: tuple[User, TenantUser],
    tenant: Tenant,
    db: AsyncSession,
) -> None:
    alice, alice_tu = user_alice
    manager = await _make_manager(db, tenant)
    alice_tu.manager_user_id = manager.id  # alice の上長を manager に設定
    report = WeeklyReport(
        user_id=alice.id, week_start_date="2026-06-22", feeling="ok", status="submitted"
    )
    db.add(report)
    await db.flush()
    db.add(WeeklyReportFeedback(report_id=report.id, manager_user_id=manager.id, comment="good"))
    await db.commit()

    resp = await alice_client.get("/api/weekly-reports/unread-feedback-count")
    assert resp.status_code == 200
    assert resp.json()["count"] == 1
    assert resp.json()["latest_unread_week_start_date"] == "2026-06-22"


@pytest.mark.asyncio
async def test_mark_read_clears_only_viewed_report_and_other_users_unaffected(
    alice_client: AsyncClient,
    bob_client: AsyncClient,
    user_alice: tuple[User, TenantUser],
    user_bob: tuple[User, TenantUser],
    tenant: Tenant,
    db: AsyncSession,
) -> None:
    alice, alice_tu = user_alice
    bob, bob_tu = user_bob
    manager = await _make_manager(db, tenant)
    alice_tu.manager_user_id = manager.id
    bob_tu.manager_user_id = manager.id
    alice_old_report = WeeklyReport(
        user_id=alice.id, week_start_date="2026-06-15", feeling="ok", status="submitted"
    )
    alice_latest_report = WeeklyReport(
        user_id=alice.id, week_start_date="2026-06-22", feeling="ok", status="submitted"
    )
    bob_report = WeeklyReport(
        user_id=bob.id, week_start_date="2026-06-22", feeling="ok", status="submitted"
    )
    db.add_all([alice_old_report, alice_latest_report, bob_report])
    await db.flush()
    db.add_all(
        [
            WeeklyReportFeedback(
                report_id=alice_old_report.id,
                manager_user_id=manager.id,
                comment="old",
                created_at=datetime(2026, 7, 2, tzinfo=timezone.utc),
            ),
            WeeklyReportFeedback(
                report_id=alice_latest_report.id,
                manager_user_id=manager.id,
                comment="latest",
                created_at=datetime(2026, 7, 1, tzinfo=timezone.utc),
            ),
            WeeklyReportFeedback(
                report_id=bob_report.id,
                manager_user_id=manager.id,
                comment="bob",
                created_at=datetime(2026, 7, 1, tzinfo=timezone.utc),
            ),
        ]
    )
    await db.commit()

    unread = (await alice_client.get("/api/weekly-reports/unread-feedback-count")).json()
    assert unread == {"count": 2, "latest_unread_week_start_date": "2026-06-22"}

    mark_read = await alice_client.post(
        f"/api/weekly-reports/{alice_latest_report.id}/feedback/mark-read"
    )
    assert mark_read.status_code == 200
    assert (
        await alice_client.post(
            f"/api/weekly-reports/{bob_report.id}/feedback/mark-read"
        )
    ).status_code == 404

    remaining = (await alice_client.get("/api/weekly-reports/unread-feedback-count")).json()
    assert remaining == {"count": 1, "latest_unread_week_start_date": "2026-06-15"}
    assert (await bob_client.get("/api/weekly-reports/unread-feedback-count")).json()["count"] == 1
