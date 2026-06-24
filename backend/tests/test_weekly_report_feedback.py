"""週報フィードバックの未読バッジ関連エンドポイントのテスト。"""

import uuid

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
