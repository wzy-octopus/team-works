from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import create_access_token, get_current_user, verify_password
from app.models.models import Project, ProjectMember, Tenant, TenantUser, User
from app.schemas.auth import LoginRequest, TenantInfo, TokenResponse, UserResponse

router = APIRouter()


@router.post("/login", response_model=TokenResponse)
async def login(body: LoginRequest, db: AsyncSession = Depends(get_db)) -> TokenResponse:
    """email + password 認証 → JWT + テナント一覧を返す。"""
    result = await db.execute(select(User).where(User.email == body.email))
    user = result.scalar_one_or_none()

    if not user or not verify_password(body.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    # 所属テナント一覧を取得
    tu_result = await db.execute(
        select(TenantUser).where(TenantUser.user_id == user.id, TenantUser.is_active == True)  # noqa: E712
    )
    tenant_users = tu_result.scalars().all()

    if not tenant_users:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User has no tenant membership",
        )

    # テナント名を取得
    tenant_ids = [tu.tenant_id for tu in tenant_users]
    tenants_result = await db.execute(select(Tenant).where(Tenant.id.in_(tenant_ids)))
    tenants = {t.id: t for t in tenants_result.scalars().all()}

    tenant_info_list = [
        TenantInfo(id=tid, name=tenants[tid].name)
        for tid in tenant_ids
        if tid in tenants
    ]

    # last_login_at を更新
    user.last_login_at = datetime.now(timezone.utc)
    await db.commit()

    # JWT には user_id と最初のテナントIDを格納（X-Tenant-ID ヘッダーで上書き可能）
    first_tenant_id = tenant_users[0].tenant_id
    token = create_access_token({"sub": user.id, "tenant_id": first_tenant_id})

    # role は最初のテナントのものを参照
    first_tu = tenant_users[0]

    # 最初のテナント内で本人が所属するプロジェクトIDを返す（ログイン直後の空配列を防ぐ）
    pm_result = await db.execute(
        select(ProjectMember.project_id)
        .join(Project, Project.id == ProjectMember.project_id)
        .where(
            ProjectMember.user_id == user.id,
            Project.tenant_id == first_tenant_id,
        )
    )
    project_ids = [row[0] for row in pm_result.all()]

    return TokenResponse(
        access_token=token,
        token_type="bearer",
        user=UserResponse(
            id=user.id,
            email=user.email,
            name=user.name,
            role=first_tu.role,
            project_ids=project_ids,
        ),
        tenants=tenant_info_list,
    )


@router.get("/me", response_model=UserResponse)
async def me(
    current_user: dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> UserResponse:
    """現在の認証済みユーザー情報を返す。

    project_ids には、現在のテナント内で本人が所属するプロジェクトの ID のみを含める（BUG-021）。
    """
    pm_result = await db.execute(
        select(ProjectMember.project_id)
        .join(Project, Project.id == ProjectMember.project_id)
        .where(
            ProjectMember.user_id == current_user["id"],
            Project.tenant_id == current_user["tenant_id"],
        )
    )
    project_ids = [row[0] for row in pm_result.all()]

    return UserResponse(
        id=current_user["id"],
        email=current_user["email"],
        name=current_user["name"],
        role=current_user["role"],
        project_ids=project_ids,
    )
