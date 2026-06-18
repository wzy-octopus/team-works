from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dates import business_today
from app.core.security import get_current_user
from app.models.models import Project, ProjectMember, Task
from app.schemas.task import TaskCreate, TaskListResponse, TaskResponse, TaskUpdate

router = APIRouter()


@router.get("", response_model=TaskListResponse)
async def list_tasks(
    task_date: str | None = Query(None, description="YYYY-MM-DD。省略時は当日"),
    project_id: str | None = Query(None),
    current_user: dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> TaskListResponse:
    """当日のマイタスク一覧を返す。"""
    target_date = task_date or business_today()

    stmt = select(Task).where(
        Task.user_id == current_user["id"],
        Task.task_date == target_date,
    )
    if project_id:
        stmt = stmt.where(Task.project_id == project_id)

    result = await db.execute(stmt)
    tasks = result.scalars().all()
    return TaskListResponse(tasks=[TaskResponse.model_validate(t) for t in tasks])


@router.post("", response_model=TaskResponse, status_code=status.HTTP_201_CREATED)
async def create_task(
    body: TaskCreate,
    current_user: dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> TaskResponse:
    """新しいタスクを作成する。

    project_id を指定する場合は、同一テナントのプロジェクトであり、かつ本人がそのプロジェクトの
    メンバー（ProjectMember）であることを必須とする（BUG-021）。project_id 未指定（個人タスク）は許可。
    """
    if body.project_id is not None:
        proj_result = await db.execute(
            select(Project).where(
                Project.id == body.project_id,
                Project.tenant_id == current_user["tenant_id"],
            )
        )
        if proj_result.scalar_one_or_none() is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Project not found"
            )

        member_result = await db.execute(
            select(ProjectMember).where(
                ProjectMember.project_id == body.project_id,
                ProjectMember.user_id == current_user["id"],
            )
        )
        if member_result.scalar_one_or_none() is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You are not a member of this project",
            )

    task = Task(
        user_id=current_user["id"],
        name=body.name,
        estimated_hours=body.estimated_hours,
        project_id=body.project_id,
        is_private=body.is_private,
        task_date=body.task_date,
    )
    db.add(task)
    await db.commit()
    await db.refresh(task)
    return TaskResponse.model_validate(task)


@router.patch("/{task_id}", response_model=TaskResponse)
async def update_task(
    task_id: str,
    body: TaskUpdate,
    current_user: dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> TaskResponse:
    """タスクを更新する（自分のタスクのみ）。"""
    result = await db.execute(
        select(Task).where(Task.id == task_id, Task.user_id == current_user["id"])
    )
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")

    update_data = body.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(task, field, value)

    await db.commit()
    await db.refresh(task)
    return TaskResponse.model_validate(task)


@router.delete("/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_task(
    task_id: str,
    current_user: dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """タスクを削除する（自分のタスクのみ）。"""
    result = await db.execute(
        select(Task).where(Task.id == task_id, Task.user_id == current_user["id"])
    )
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")

    await db.delete(task)
    await db.commit()
