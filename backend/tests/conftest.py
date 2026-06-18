import uuid

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.database import Base, get_db
from app.core.security import create_access_token, hash_password
from app.main import app
from app.models.models import Project, ProjectMember, Tenant, TenantUser, User

TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

test_engine = create_async_engine(TEST_DATABASE_URL, echo=False)
TestSessionLocal = async_sessionmaker(test_engine, expire_on_commit=False)


async def override_get_db():
    async with TestSessionLocal() as session:
        yield session


app.dependency_overrides[get_db] = override_get_db


@pytest_asyncio.fixture(scope="session", autouse=True)
async def setup_database():
    """テスト用インメモリDBのテーブルを作成する。"""
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture
async def db() -> AsyncSession:
    async with TestSessionLocal() as session:
        yield session


@pytest_asyncio.fixture
async def tenant(db: AsyncSession) -> Tenant:
    t = Tenant(name=f"Test Tenant {uuid.uuid4().hex[:8]}")
    db.add(t)
    await db.commit()
    await db.refresh(t)
    return t


@pytest_asyncio.fixture
async def user_alice(db: AsyncSession, tenant: Tenant) -> tuple[User, TenantUser]:
    """テナント内の一般メンバー（alice）。テストごとにユニークなメールアドレスを使用。"""
    unique_suffix = uuid.uuid4().hex[:8]
    user = User(
        email=f"alice_{unique_suffix}@example.com",
        name="Alice",
        hashed_password=hash_password("password123"),
    )
    db.add(user)
    await db.flush()

    tu = TenantUser(tenant_id=tenant.id, user_id=user.id, role="member")
    db.add(tu)
    await db.commit()
    await db.refresh(user)
    await db.refresh(tu)
    return user, tu


@pytest_asyncio.fixture
async def user_bob(db: AsyncSession, tenant: Tenant) -> tuple[User, TenantUser]:
    """テナント内の別の一般メンバー（bob）。テストごとにユニークなメールアドレスを使用。"""
    unique_suffix = uuid.uuid4().hex[:8]
    user = User(
        email=f"bob_{unique_suffix}@example.com",
        name="Bob",
        hashed_password=hash_password("password123"),
    )
    db.add(user)
    await db.flush()

    tu = TenantUser(tenant_id=tenant.id, user_id=user.id, role="member")
    db.add(tu)
    await db.commit()
    await db.refresh(user)
    await db.refresh(tu)
    return user, tu


@pytest_asyncio.fixture
async def project(db: AsyncSession, tenant: Tenant) -> Project:
    """テスト用プロジェクト。"""
    proj = Project(tenant_id=tenant.id, name="Test Project", color="#6366f1")
    db.add(proj)
    await db.commit()
    await db.refresh(proj)
    return proj


@pytest_asyncio.fixture
async def project_with_members(
    db: AsyncSession,
    project: Project,
    user_alice: tuple[User, TenantUser],
    user_bob: tuple[User, TenantUser],
) -> Project:
    """AliceとBobを追加したテスト用プロジェクト。"""
    alice, _ = user_alice
    bob, _ = user_bob

    pm_alice = ProjectMember(project_id=project.id, user_id=alice.id)
    pm_bob = ProjectMember(project_id=project.id, user_id=bob.id)
    db.add(pm_alice)
    db.add(pm_bob)
    await db.commit()
    return project


def make_token(user: User, tenant: Tenant) -> str:
    return create_access_token({"sub": user.id, "tenant_id": tenant.id})


@pytest_asyncio.fixture
async def alice_client(
    user_alice: tuple[User, TenantUser], tenant: Tenant
) -> AsyncClient:
    """Aliceとして認証済みの非同期HTTPクライアント。"""
    alice, _ = user_alice
    token = make_token(alice, tenant)
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        headers={"Authorization": f"Bearer {token}"},
    ) as client:
        yield client


@pytest_asyncio.fixture
async def bob_client(
    user_bob: tuple[User, TenantUser], tenant: Tenant
) -> AsyncClient:
    """Bobとして認証済みの非同期HTTPクライアント。"""
    bob, _ = user_bob
    token = make_token(bob, tenant)
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        headers={"Authorization": f"Bearer {token}"},
    ) as client:
        yield client


@pytest_asyncio.fixture
async def user_admin(db: AsyncSession, tenant: Tenant) -> tuple[User, TenantUser]:
    """テナント内の管理者ユーザー。テストごとにユニークなメールアドレスを使用。"""
    unique_suffix = uuid.uuid4().hex[:8]
    user = User(
        email=f"admin_{unique_suffix}@example.com",
        name="Admin",
        hashed_password=hash_password("password123"),
    )
    db.add(user)
    await db.flush()

    tu = TenantUser(tenant_id=tenant.id, user_id=user.id, role="admin")
    db.add(tu)
    await db.commit()
    await db.refresh(user)
    await db.refresh(tu)
    return user, tu


@pytest_asyncio.fixture
async def admin_client(
    user_admin: tuple[User, TenantUser], tenant: Tenant
) -> AsyncClient:
    """管理者として認証済みの非同期HTTPクライアント。"""
    admin, _ = user_admin
    token = make_token(admin, tenant)
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        headers={"Authorization": f"Bearer {token}"},
    ) as client:
        yield client
