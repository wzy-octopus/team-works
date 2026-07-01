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
WEEK_DAYS = 7


def _week_dates(week_start: str) -> list[str]:
    """week_start（月曜日想定）から7日間（月〜日）の YYYY-MM-DD リストを返す。"""
    start = date.fromisoformat(week_start)
    return [(start + timedelta(days=offset)).isoformat() for offset in range(WEEK_DAYS)]


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


@router.get("/week")
async def get_dashboard_week(
    project_id: str = Query(..., description="プロジェクトID（必須）"),
    week_start: str = Query(..., description="YYYY-MM-DD（月曜日）"),
    current_user: dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """指定プロジェクトの1週間（月〜日）のメンバー別・日別タスク集計を返す。

    集計規則は単日ダッシュボードと同一:
    - 自分のタスクは private を含めて status 別に集計する。
    - 他メンバーは公開タスクのみ status 別に集計し、private は件数（private_count）としてのみ返す。
    アクセス制御も単日と同一（admin はテナント内全 project、それ以外は所属 project のみ）。
    看板の週グリッド（状態×日）はフロントでメンバー横断に合算して導出する。
    """
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
        select(ProjectMember)
        .options(selectinload(ProjectMember.user))
        .where(ProjectMember.project_id == project_id)
    )
    members = members_result.scalars().all()
    member_user_ids = [m.user_id for m in members]

    # アクセス制御（BUG-024 と同一）: admin はテナント内全 project、それ以外は所属 project のみ。
    if current_user["role"] != "admin" and current_user_id not in member_user_ids:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not a member of this project",
        )

    if not members:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project has no members")

    days = _week_dates(week_start)
    start_date, end_date = days[0], days[-1]
    other_user_ids = [uid for uid in member_user_ids if uid != current_user_id]

    # 自分のタスクは private も含めて全件取得する
    # （単日ダッシュボードで自分の private が見えるのと同じ扱い）。
    own_result = await db.execute(
        select(Task)
        .options(selectinload(Task.user))
        .where(
            Task.user_id == current_user_id,
            Task.project_id == project_id,
            Task.task_date >= start_date,
            Task.task_date <= end_date,
        )
    )
    detail_tasks = list(own_result.scalars().all())

    # 他メンバーは公開タスクのみ取得する（private の詳細は返さない）。
    if other_user_ids:
        other_result = await db.execute(
            select(Task)
            .options(selectinload(Task.user))
            .where(
                Task.user_id.in_(other_user_ids),
                Task.project_id == project_id,
                Task.task_date >= start_date,
                Task.task_date <= end_date,
                Task.is_private == False,  # noqa: E712
            )
        )
        detail_tasks.extend(other_result.scalars().all())

    # 他メンバーの private は件数のみ返す（(user_id, task_date) 単位）。
    private_counts: dict[tuple[str, str], int] = {}
    if other_user_ids:
        private_result = await db.execute(
            select(Task.user_id, Task.task_date, func.count())
            .where(
                Task.user_id.in_(other_user_ids),
                Task.project_id == project_id,
                Task.task_date >= start_date,
                Task.task_date <= end_date,
                Task.is_private == True,  # noqa: E712
            )
            .group_by(Task.user_id, Task.task_date)
        )
        for uid, task_date, count in private_result.all():
            private_counts[(uid, task_date)] = count

    # status 集計は取得済みタスクから Python 側で作る
    # （自分=private 込み / 他人=公開のみ、が detail_tasks の時点で担保されている）。
    status_counts: dict[tuple[str, str, str], int] = {}
    for t in detail_tasks:
        key = (t.user_id, t.task_date, t.status)
        status_counts[key] = status_counts.get(key, 0) + 1

    members_payload = [
        {
            "user_id": m.user_id,
            "user_name": m.user.name,
            "days": [
                {
                    "date": d,
                    "todo": status_counts.get((m.user_id, d, "todo"), 0),
                    "in_progress": status_counts.get((m.user_id, d, "in_progress"), 0),
                    "done": status_counts.get((m.user_id, d, "done"), 0),
                    "private_count": private_counts.get((m.user_id, d), 0),
                }
                for d in days
            ],
        }
        for m in members
    ]

    # 人名展開用のタスク明細（自分=全件・他人=公開のみ）。private の詳細は含まれない。
    tasks = [
        {
            "id": t.id,
            "user_id": t.user_id,
            "user_name": t.user.name,
            "name": t.name,
            "status": t.status,
            "is_private": t.is_private,
            "task_date": t.task_date,
            "estimated_hours": t.estimated_hours,
        }
        for t in detail_tasks
    ]

    return {
        "week_start": week_start,
        "days": days,
        "members": members_payload,
        "tasks": tasks,
    }
