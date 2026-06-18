from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.core.dates import business_today
from app.core.security import get_current_user
from app.models.models import Project, ProjectMember, Task

router = APIRouter()


@router.get("")
async def get_dashboard(
    project_id: str = Query(..., description="プロジェクトID（必須）"),
    task_date: str | None = Query(None, description="YYYY-MM-DD。省略時は当日"),
    current_user: dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """指定プロジェクトの当日全メンバーのタスク一覧と非公開タスク件数を返す。

    is_private=true のタスクは本人以外には返さないが、件数は private_counts に含める。
    """
    target_date = task_date or business_today()
    current_user_id = current_user["id"]

    project_result = await db.execute(
        select(Project).where(
            Project.id == project_id,
            Project.tenant_id == current_user["tenant_id"],
        )
    )
    project = project_result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    members_result = await db.execute(
        select(ProjectMember).where(ProjectMember.project_id == project_id)
    )
    members = members_result.scalars().all()
    if not members:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project has no members")

    member_user_ids = [m.user_id for m in members]

    # 自分のタスク（全件）
    result_mine = await db.execute(
        select(Task)
        .options(selectinload(Task.user))
        .where(
            Task.user_id == current_user_id,
            Task.task_date == target_date,
            Task.project_id == project_id,
        )
    )
    my_tasks = list(result_mine.scalars().all())

    # 他メンバーの公開タスク + プライベートタスク件数
    other_user_ids = [uid for uid in member_user_ids if uid != current_user_id]
    other_tasks: list[Task] = []
    private_counts: dict[str, int] = {}

    for uid in other_user_ids:
        result_public = await db.execute(
            select(Task)
            .options(selectinload(Task.user))
            .where(
                Task.user_id == uid,
                Task.task_date == target_date,
                Task.project_id == project_id,
                Task.is_private == False,  # noqa: E712
            )
        )
        other_tasks.extend(result_public.scalars().all())

        count_result = await db.execute(
            select(func.count()).where(
                Task.user_id == uid,
                Task.task_date == target_date,
                Task.project_id == project_id,
                Task.is_private == True,  # noqa: E712
            )
        )
        private_counts[uid] = count_result.scalar_one()

    tasks = [
        {
            "id": t.id,
            "user_id": t.user_id,
            "user_name": t.user.name,
            "project_id": t.project_id,
            "project_name": project.name,
            "project_color": project.color,
            "name": t.name,
            "estimated_hours": t.estimated_hours,
            "status": t.status,
            "is_private": t.is_private,
            "task_date": t.task_date,
            "created_at": t.created_at.isoformat(),
            "updated_at": t.created_at.isoformat(),
        }
        for t in my_tasks + other_tasks
    ]

    return {"tasks": tasks, "private_counts": private_counts}
