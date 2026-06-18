import secrets
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user, hash_password, require_admin
from app.models.models import Project, ProjectMember, TenantUser, User
from app.schemas.admin import (
    InviteRequest,
    MemberResponse,
    ProjectCreate,
    ProjectResponse,
    TenantUserUpdate,
)

router = APIRouter()


async def _build_member_response(tu: TenantUser, user: User, db: AsyncSession) -> MemberResponse:
    pm_result = await db.execute(
        select(ProjectMember).where(ProjectMember.user_id == user.id)
    )
    project_ids = [pm.project_id for pm in pm_result.scalars().all()]
    return MemberResponse(
        id=tu.id,
        user_id=user.id,
        name=user.name,
        email=user.email,
        role=tu.role,
        manager_user_id=tu.manager_user_id,
        project_ids=project_ids,
        last_login_at=user.last_login_at,
    )


# ---------------------------------------------------------------------------
# プロジェクト一覧（全ユーザー向け）
# ---------------------------------------------------------------------------


@router.get("/projects", response_model=list[ProjectResponse])
async def list_projects(
    current_user: dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[ProjectResponse]:
    """テナントのプロジェクト一覧を返す（全認証ユーザーが参照可能）。"""
    tenant_id = current_user["tenant_id"]

    projects_result = await db.execute(
        select(Project).where(Project.tenant_id == tenant_id)
    )
    projects = projects_result.scalars().all()

    responses: list[ProjectResponse] = []
    for project in projects:
        count_result = await db.execute(
            select(func.count()).where(ProjectMember.project_id == project.id)
        )
        member_count = count_result.scalar_one()
        responses.append(
            ProjectResponse(
                id=project.id,
                name=project.name,
                color=project.color,
                description=project.description,
                member_count=member_count,
            )
        )

    return responses


@router.post("/projects", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
async def create_project(
    body: ProjectCreate,
    current_user: dict[str, Any] = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> ProjectResponse:
    """プロジェクトを作成する（管理者のみ）。"""
    project = Project(
        tenant_id=current_user["tenant_id"],
        name=body.name,
        color=body.color,
        description=body.description,
    )
    db.add(project)
    await db.commit()
    await db.refresh(project)

    return ProjectResponse(
        id=project.id,
        name=project.name,
        color=project.color,
        description=project.description,
        member_count=0,
    )


@router.post("/projects/{project_id}/members", status_code=status.HTTP_201_CREATED)
async def add_project_member(
    project_id: str,
    user_id: str,
    current_user: dict[str, Any] = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    """プロジェクトにメンバーを追加する。"""
    proj_result = await db.execute(
        select(Project).where(
            Project.id == project_id, Project.tenant_id == current_user["tenant_id"]
        )
    )
    if not proj_result.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    # 追加対象ユーザーが同一テナントに所属していることを検証する（テナント隔離）
    target_tu = await db.execute(
        select(TenantUser).where(
            TenantUser.tenant_id == current_user["tenant_id"],
            TenantUser.user_id == user_id,
        )
    )
    if not target_tu.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    existing = await db.execute(
        select(ProjectMember).where(
            ProjectMember.project_id == project_id, ProjectMember.user_id == user_id
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="User is already a member")

    db.add(ProjectMember(project_id=project_id, user_id=user_id))
    await db.commit()
    return {"message": "Member added successfully"}


@router.delete("/projects/{project_id}/members/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_project_member(
    project_id: str,
    user_id: str,
    current_user: dict[str, Any] = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> None:
    """プロジェクトからメンバーを除外する。"""
    proj_result = await db.execute(
        select(Project).where(
            Project.id == project_id, Project.tenant_id == current_user["tenant_id"]
        )
    )
    if not proj_result.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    result = await db.execute(
        select(ProjectMember).where(
            ProjectMember.project_id == project_id, ProjectMember.user_id == user_id
        )
    )
    member = result.scalar_one_or_none()
    if not member:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Member not found")
    await db.delete(member)
    await db.commit()


# ---------------------------------------------------------------------------
# メンバー管理（管理者のみ）
# ---------------------------------------------------------------------------


@router.get("/members", response_model=list[MemberResponse])
async def list_members(
    current_user: dict[str, Any] = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> list[MemberResponse]:
    """テナントのメンバー一覧を返す。"""
    tu_result = await db.execute(
        select(TenantUser).where(TenantUser.tenant_id == current_user["tenant_id"])
    )
    tenant_users = tu_result.scalars().all()

    members: list[MemberResponse] = []
    for tu in tenant_users:
        user_result = await db.execute(select(User).where(User.id == tu.user_id))
        user = user_result.scalar_one_or_none()
        if user:
            members.append(await _build_member_response(tu, user, db))

    return members


@router.patch("/members/{user_id}", response_model=MemberResponse)
async def update_member(
    user_id: str,
    body: TenantUserUpdate,
    current_user: dict[str, Any] = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> MemberResponse:
    """メンバーのロール・上長を変更する。"""
    tu_result = await db.execute(
        select(TenantUser).where(
            TenantUser.tenant_id == current_user["tenant_id"],
            TenantUser.user_id == user_id,
        )
    )
    tu = tu_result.scalar_one_or_none()
    if not tu:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Member not found")

    if body.role is not None:
        tu.role = body.role
    if body.clear_manager:
        tu.manager_user_id = None
    elif body.manager_user_id is not None:
        tu.manager_user_id = body.manager_user_id

    await db.commit()

    user_result = await db.execute(select(User).where(User.id == user_id))
    user = user_result.scalar_one()
    return await _build_member_response(tu, user, db)


@router.delete("/members/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_member(
    user_id: str,
    current_user: dict[str, Any] = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> None:
    """テナントからメンバーを削除する（TenantUser レコードを削除）。"""
    tu_result = await db.execute(
        select(TenantUser).where(
            TenantUser.tenant_id == current_user["tenant_id"],
            TenantUser.user_id == user_id,
        )
    )
    tu = tu_result.scalar_one_or_none()
    if not tu:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Member not found")

    await db.delete(tu)
    await db.commit()


# ---------------------------------------------------------------------------
# 招待
# ---------------------------------------------------------------------------


@router.post("/invite", status_code=status.HTTP_201_CREATED)
async def invite_member(
    body: InviteRequest,
    current_user: dict[str, Any] = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    """指定メールのユーザーをテナントに追加する。未登録の場合は新規ユーザーを作成する。"""
    tenant_id = current_user["tenant_id"]

    user_result = await db.execute(select(User).where(User.email == body.email))
    user = user_result.scalar_one_or_none()

    temp_password: str | None = None
    if user is None:
        temp_password = secrets.token_urlsafe(12)
        user = User(
            email=body.email,
            name=body.name or body.email.split("@")[0],
            hashed_password=hash_password(temp_password),
        )
        db.add(user)
        await db.flush()

    existing_tu = await db.execute(
        select(TenantUser).where(
            TenantUser.tenant_id == tenant_id,
            TenantUser.user_id == user.id,
        )
    )
    if existing_tu.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="User is already a member of this tenant",
        )

    db.add(TenantUser(tenant_id=tenant_id, user_id=user.id, role=body.role))
    await db.commit()

    if temp_password:
        return {
            "message": f"{body.email} をテナントに追加しました。",
            "temp_password": temp_password,
        }
    return {"message": f"{body.email} をテナントに追加しました。"}
