from datetime import date, timedelta
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

PAST_INCOMPLETE_DAYS = 30
INCOMPLETE_STATUSES = ("todo", "in_progress")


def _past_incomplete_dates(today_str: str) -> list[str]:
    today = date.fromisoformat(today_str)
    return [
        (today - timedelta(days=offset)).isoformat()
        for offset in range(1, PAST_INCOMPLETE_DAYS + 1)
    ]


async def _build_past_incomplete_summary(
    *,
    db: AsyncSession,
    project_id: str,
    current_user_id: str,
    member_user_ids: list[str],
    today_str: str,
) -> dict[str, Any]:
    dates = _past_incomplete_dates(today_str)
    counts_by_date = dict.fromkeys(dates, 0)
    start_date = dates[-1]
    end_date = dates[0]

    own_result = await db.execute(
        select(Task.task_date, func.count())
        .where(
            Task.user_id == current_user_id,
            Task.project_id == project_id,
            Task.task_date >= start_date,
            Task.task_date <= end_date,
            Task.status.in_(INCOMPLETE_STATUSES),
        )
        .group_by(Task.task_date)
    )
    for task_date, count in own_result.all():
        counts_by_date[task_date] += count

    other_user_ids = [uid for uid in member_user_ids if uid != current_user_id]
    if other_user_ids:
        other_result = await db.execute(
            select(Task.task_date, func.count())
            .where(
                Task.user_id.in_(other_user_ids),
                Task.project_id == project_id,
                Task.task_date >= start_date,
                Task.task_date <= end_date,
                Task.status.in_(INCOMPLETE_STATUSES),
                Task.is_private == False,  # noqa: E712
            )
            .group_by(Task.task_date)
        )
        for task_date, count in other_result.all():
            counts_by_date[task_date] += count

    items = [
        {"task_date": task_date, "count": counts_by_date[task_date]}
        for task_date in dates
    ]
    return {"total": sum(counts_by_date.values()), "items": items}


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
    today_str = business_today()
    target_date = task_date or today_str
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
    member_user_ids = [m.user_id for m in members]

    # アクセス制御（BUG-024）: admin はテナント内の全 project を閲覧可。
    # manager/member は自分が ProjectMember として所属する project のみ閲覧可。
    # フロントの非表示だけに頼らず、後端で必ず兜底する。
    if current_user["role"] != "admin" and current_user_id not in member_user_ids:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not a member of this project",
        )

    if not members:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project has no members")

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

    past_incomplete_summary = await _build_past_incomplete_summary(
        db=db,
        project_id=project_id,
        current_user_id=current_user_id,
        member_user_ids=member_user_ids,
        today_str=today_str,
    )

    return {
        "tasks": tasks,
        "private_counts": private_counts,
        "past_incomplete_summary": past_incomplete_summary,
    }
