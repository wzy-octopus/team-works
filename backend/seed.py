"""ローカル開発用シードデータを投入するスクリプト。"""

import asyncio

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.config import settings
from app.core.security import hash_password
from app.models.models import (
    Base,
    Project,
    ProjectMember,
    Tenant,
    TenantUser,
    User,
)

engine = create_async_engine(settings.DATABASE_URL, echo=False)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False)


async def seed() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with SessionLocal() as db:
        # テナント
        tenant = Tenant(name="MCTジャパン株式会社")
        db.add(tenant)
        await db.flush()

        # ユーザー
        admin = User(
            email="admin@example.com",
            name="管理者 太郎",
            hashed_password=hash_password("password"),
        )
        manager = User(
            email="manager@example.com",
            name="上長 花子",
            hashed_password=hash_password("password"),
        )
        member1 = User(
            email="alice@example.com",
            name="山田 アリス",
            hashed_password=hash_password("password"),
        )
        member2 = User(
            email="bob@example.com",
            name="鈴木 ボブ",
            hashed_password=hash_password("password"),
        )
        for u in [admin, manager, member1, member2]:
            db.add(u)
        await db.flush()

        # テナントユーザー（manager が admin/member1/member2 の上長）
        tu_admin = TenantUser(tenant_id=tenant.id, user_id=admin.id, role="admin")
        tu_manager = TenantUser(
            tenant_id=tenant.id,
            user_id=manager.id,
            role="manager",
        )
        tu_m1 = TenantUser(
            tenant_id=tenant.id,
            user_id=member1.id,
            role="member",
            manager_user_id=manager.id,
        )
        tu_m2 = TenantUser(
            tenant_id=tenant.id,
            user_id=member2.id,
            role="member",
            manager_user_id=manager.id,
        )
        for tu in [tu_admin, tu_manager, tu_m1, tu_m2]:
            db.add(tu)
        await db.flush()

        # プロジェクト
        proj1 = Project(tenant_id=tenant.id, name="Webリニューアル", color="#6c63ff")
        proj2 = Project(tenant_id=tenant.id, name="モバイルアプリ", color="#00d4aa")
        for p in [proj1, proj2]:
            db.add(p)
        await db.flush()

        # プロジェクトメンバー
        for user_id in [admin.id, manager.id, member1.id, member2.id]:
            db.add(ProjectMember(project_id=proj1.id, user_id=user_id))
        for user_id in [manager.id, member1.id]:
            db.add(ProjectMember(project_id=proj2.id, user_id=user_id))

        await db.commit()

    print("OK: シードデータを投入しました")
    print()
    print("ログインアカウント (password: password)")
    print("  admin@example.com   / 管理者")
    print("  manager@example.com / 上長")
    print("  alice@example.com   / メンバー")
    print("  bob@example.com     / メンバー")

    await engine.dispose()


asyncio.run(seed())
