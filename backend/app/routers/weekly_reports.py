import asyncio
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.models import (
    Task,
    TenantUser,
    User,
    WeeklyReport,
    WeeklyReportFeedback,
    WeeklyReportReaction,
)
from app.services.ai_summary import generate_weekly_summary
from app.schemas.weekly_report import (
    FeedbackCreate,
    FeedbackResponse,
    InboxReportResponse,
    WeeklyReportCreate,
    WeeklyReportResponse,
    WeeklyReportUpdate,
)

router = APIRouter()


def _report_to_response(report: WeeklyReport) -> WeeklyReportResponse:
    return WeeklyReportResponse(
        id=report.id,
        user_id=report.user_id,
        week_start_date=report.week_start_date,
        ai_summary=report.ai_summary,
        feeling=report.feeling,
        questions=report.questions,
        issues=report.issues,
        status=report.status,
        submitted_at=report.submitted_at,
        created_at=report.created_at,
    )


def _feedback_to_response(feedback: WeeklyReportFeedback) -> FeedbackResponse:
    return FeedbackResponse(
        id=feedback.id,
        manager_user_id=feedback.manager_user_id,
        comment=feedback.comment,
        reactions=[r.reaction_type for r in feedback.reactions],
        created_at=feedback.created_at,
    )


# ---------------------------------------------------------------------------
# 受信トレイ（/inbox は /{report_id} より先に定義する必要がある）
# ---------------------------------------------------------------------------


@router.get("/inbox", response_model=list[InboxReportResponse])
async def list_inbox(
    week_start_date: str | None = Query(None),
    current_user: dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[InboxReportResponse]:
    """上長として担当メンバーの週報一覧を返す。week_start_date で週フィルタ可能。"""
    tu_result = await db.execute(
        select(TenantUser).where(
            TenantUser.tenant_id == current_user["tenant_id"],
            TenantUser.manager_user_id == current_user["id"],
        )
    )
    subordinate_ids = [tu.user_id for tu in tu_result.scalars().all()]

    if not subordinate_ids:
        return []

    stmt = select(WeeklyReport, User).join(User, User.id == WeeklyReport.user_id).where(
        WeeklyReport.user_id.in_(subordinate_ids)
    )
    if week_start_date:
        stmt = stmt.where(WeeklyReport.week_start_date == week_start_date)

    rows = (await db.execute(stmt)).all()

    return [
        InboxReportResponse(
            id=report.id,
            user_id=report.user_id,
            week_start_date=report.week_start_date,
            ai_summary=report.ai_summary,
            feeling=report.feeling,
            questions=report.questions,
            issues=report.issues,
            status=report.status,
            submitted_at=report.submitted_at,
            created_at=report.created_at,
            user_name=user.name,
            user_email=user.email,
        )
        for report, user in rows
    ]


# ---------------------------------------------------------------------------
# 未読フィードバック（バッジ用。/{report_id} より前に定義する）
# ---------------------------------------------------------------------------


@router.get("/unread-feedback-count")
async def unread_feedback_count(
    current_user: dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, int | str | None]:
    """未読フィードバック件数と最新の対象週を返す。"""
    latest_fb = (
        select(
            WeeklyReportFeedback.report_id.label("report_id"),
            func.max(WeeklyReportFeedback.created_at).label("last_fb"),
        )
        .group_by(WeeklyReportFeedback.report_id)
        .subquery()
    )
    stmt = (
        select(func.count())
        .select_from(WeeklyReport)
        .join(latest_fb, latest_fb.c.report_id == WeeklyReport.id)
        .where(
            WeeklyReport.user_id == current_user["id"],
            or_(
                WeeklyReport.feedback_seen_at.is_(None),
                latest_fb.c.last_fb > WeeklyReport.feedback_seen_at,
            ),
        )
    )
    count = (await db.execute(stmt)).scalar_one()
    latest_week_stmt = (
        select(WeeklyReport.week_start_date)
        .join(latest_fb, latest_fb.c.report_id == WeeklyReport.id)
        .where(
            WeeklyReport.user_id == current_user["id"],
            or_(
                WeeklyReport.feedback_seen_at.is_(None),
                latest_fb.c.last_fb > WeeklyReport.feedback_seen_at,
            ),
        )
        .order_by(WeeklyReport.week_start_date.desc())
        .limit(1)
    )
    latest_week = (await db.execute(latest_week_stmt)).scalar_one_or_none()
    return {"count": count, "latest_unread_week_start_date": latest_week}


@router.post("/{report_id}/feedback/mark-read")
async def mark_report_feedback_read(
    report_id: str,
    current_user: dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, bool]:
    """表示した本人の週報フィードバックだけを既読化する。"""
    report = (
        await db.execute(
            select(WeeklyReport).where(
                WeeklyReport.id == report_id,
                WeeklyReport.user_id == current_user["id"],
            )
        )
    ).scalar_one_or_none()
    if not report:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Report not found",
        )

    report.feedback_seen_at = datetime.now(timezone.utc)
    await db.commit()
    return {"read": True}


@router.post("/feedback/mark-read")
async def mark_feedback_read(
    current_user: dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, int]:
    """本人の週報のフィードバックを全て既読化する（feedback_seen_at を now に更新）。"""
    now = datetime.now(timezone.utc)
    reports = (
        await db.execute(
            select(WeeklyReport).where(WeeklyReport.user_id == current_user["id"])
        )
    ).scalars().all()
    for report in reports:
        report.feedback_seen_at = now
    await db.commit()
    return {"count": 0}


# ---------------------------------------------------------------------------
# 週報の取得 or 作成（current エンドポイント）
# ---------------------------------------------------------------------------


@router.get("/current", response_model=WeeklyReportResponse)
async def get_or_create_current(
    week_start_date: str = Query(...),
    current_user: dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> WeeklyReportResponse:
    """指定週の週報を返す。なければ新規作成して返す。"""
    result = await db.execute(
        select(WeeklyReport).where(
            WeeklyReport.user_id == current_user["id"],
            WeeklyReport.week_start_date == week_start_date,
        )
    )
    report = result.scalar_one_or_none()

    if not report:
        report = WeeklyReport(
            user_id=current_user["id"],
            week_start_date=week_start_date,
            status="draft",
        )
        db.add(report)
        await db.commit()
        await db.refresh(report)

    return _report_to_response(report)


# ---------------------------------------------------------------------------
# 一覧 / 作成
# ---------------------------------------------------------------------------


@router.get("", response_model=list[WeeklyReportResponse])
async def list_my_reports(
    current_user: dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[WeeklyReportResponse]:
    """自分の週報一覧を返す。"""
    result = await db.execute(
        select(WeeklyReport).where(WeeklyReport.user_id == current_user["id"])
    )
    return [_report_to_response(r) for r in result.scalars().all()]


@router.post("", response_model=WeeklyReportResponse, status_code=status.HTTP_201_CREATED)
async def create_report(
    body: WeeklyReportCreate,
    current_user: dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> WeeklyReportResponse:
    """週報を新規作成する（同じ週に既存の場合は既存を返す）。"""
    result = await db.execute(
        select(WeeklyReport).where(
            WeeklyReport.user_id == current_user["id"],
            WeeklyReport.week_start_date == body.week_start_date,
        )
    )
    existing = result.scalar_one_or_none()
    if existing:
        return _report_to_response(existing)

    report = WeeklyReport(
        user_id=current_user["id"],
        week_start_date=body.week_start_date,
        feeling=body.feeling,
        questions=body.questions,
        issues=body.issues,
        status="draft",
    )
    db.add(report)
    await db.commit()
    await db.refresh(report)
    return _report_to_response(report)


# ---------------------------------------------------------------------------
# 個別操作（/{report_id} 系）
# ---------------------------------------------------------------------------


@router.get("/{report_id}", response_model=WeeklyReportResponse)
async def get_report(
    report_id: str,
    current_user: dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> WeeklyReportResponse:
    """週報詳細を返す（本人または担当上長のみ）。"""
    result = await db.execute(select(WeeklyReport).where(WeeklyReport.id == report_id))
    report = result.scalar_one_or_none()
    if not report:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report not found")

    if report.user_id != current_user["id"]:
        tu_result = await db.execute(
            select(TenantUser).where(
                TenantUser.user_id == report.user_id,
                TenantUser.manager_user_id == current_user["id"],
            )
        )
        if not tu_result.scalar_one_or_none():
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

    return _report_to_response(report)


@router.patch("/{report_id}", response_model=WeeklyReportResponse)
async def update_report(
    report_id: str,
    body: WeeklyReportUpdate,
    current_user: dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> WeeklyReportResponse:
    """所感・疑問・課題を更新する（本人のみ）。"""
    result = await db.execute(
        select(WeeklyReport).where(
            WeeklyReport.id == report_id,
            WeeklyReport.user_id == current_user["id"],
        )
    )
    report = result.scalar_one_or_none()
    if not report:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report not found")

    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(report, field, value)

    # feeling が入力されたら ready に昇格
    if report.feeling and report.status == "draft":
        report.status = "ready"

    await db.commit()
    await db.refresh(report)
    return _report_to_response(report)


@router.post("/{report_id}/submit", response_model=WeeklyReportResponse)
async def submit_report(
    report_id: str,
    current_user: dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> WeeklyReportResponse:
    """上長へ提出する（status → submitted）。"""
    result = await db.execute(
        select(WeeklyReport).where(
            WeeklyReport.id == report_id,
            WeeklyReport.user_id == current_user["id"],
        )
    )
    report = result.scalar_one_or_none()
    if not report:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report not found")

    if report.status in ("submitted", "feedback_received"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Report already submitted")

    if not report.feeling:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="feeling is required before submit")

    report.status = "submitted"
    report.submitted_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(report)
    return _report_to_response(report)


@router.post("/{report_id}/regenerate-summary", response_model=WeeklyReportResponse)
async def regenerate_summary(
    report_id: str,
    current_user: dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> WeeklyReportResponse:
    """対象週の公開タスクをもとに AI サマリを再生成する。"""
    result = await db.execute(
        select(WeeklyReport).where(
            WeeklyReport.id == report_id,
            WeeklyReport.user_id == current_user["id"],
        )
    )
    report = result.scalar_one_or_none()
    if not report:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report not found")

    # 週末（翌月曜）を算出してタスクを絞り込む
    from datetime import date
    week_start = date.fromisoformat(report.week_start_date)
    week_end = (week_start + timedelta(days=7)).isoformat()

    tasks_result = await db.execute(
        select(Task).where(
            Task.user_id == current_user["id"],
            Task.task_date >= report.week_start_date,
            Task.task_date < week_end,
            Task.is_private == False,  # noqa: E712
        )
    )
    task_dicts = [
        {"name": t.name, "status": t.status, "estimated_hours": t.estimated_hours}
        for t in tasks_result.scalars().all()
    ]

    try:
        summary = await asyncio.to_thread(
            generate_weekly_summary,
            report.week_start_date,
            current_user["name"],
            task_dicts,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"AI service error: {exc}",
        )

    report.ai_summary = summary
    await db.commit()
    await db.refresh(report)
    return _report_to_response(report)


# ---------------------------------------------------------------------------
# フィードバック
# ---------------------------------------------------------------------------


@router.get("/{report_id}/feedback", response_model=FeedbackResponse | None)
async def get_feedback(
    report_id: str,
    current_user: dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> FeedbackResponse | None:
    """週報に対するフィードバックを返す（なければ null）。"""
    result = await db.execute(
        select(WeeklyReportFeedback).where(WeeklyReportFeedback.report_id == report_id)
    )
    feedback = result.scalar_one_or_none()
    if not feedback:
        return None

    # reactions をロード
    await db.refresh(feedback, ["reactions"])
    return _feedback_to_response(feedback)


@router.post(
    "/{report_id}/feedback",
    response_model=FeedbackResponse,
    status_code=status.HTTP_201_CREATED,
)
async def post_feedback(
    report_id: str,
    body: FeedbackCreate,
    current_user: dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> FeedbackResponse:
    """フィードバックを送信する（コメント＋リアクション）。"""
    result = await db.execute(select(WeeklyReport).where(WeeklyReport.id == report_id))
    report = result.scalar_one_or_none()
    if not report:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report not found")

    tu_result = await db.execute(
        select(TenantUser).where(
            TenantUser.user_id == report.user_id,
            TenantUser.manager_user_id == current_user["id"],
        )
    )
    if not tu_result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not the manager of this report's owner",
        )

    feedback = WeeklyReportFeedback(
        report_id=report_id,
        manager_user_id=current_user["id"],
        comment=body.comment,
    )
    db.add(feedback)
    await db.flush()

    reactions: list[WeeklyReportReaction] = []
    for rtype in body.reaction_types:
        reaction = WeeklyReportReaction(feedback_id=feedback.id, reaction_type=rtype)
        db.add(reaction)
        reactions.append(reaction)

    report.status = "feedback_received"
    await db.commit()
    await db.refresh(feedback)

    return FeedbackResponse(
        id=feedback.id,
        manager_user_id=feedback.manager_user_id,
        comment=feedback.comment,
        reactions=[r.reaction_type for r in reactions],
        created_at=feedback.created_at,
    )
