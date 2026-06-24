import uuid
from datetime import datetime, timezone
from enum import Enum

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _uuid() -> str:
    return str(uuid.uuid4())


# ---------------------------------------------------------------------------
# Enums (str-based for SQLite compatibility)
# ---------------------------------------------------------------------------


class TaskStatus(str, Enum):
    todo = "todo"
    in_progress = "in_progress"
    done = "done"


class TenantUserRole(str, Enum):
    admin = "admin"
    manager = "manager"
    member = "member"


class WeeklyReportStatus(str, Enum):
    draft = "draft"
    ready = "ready"
    submitted = "submitted"
    feedback_received = "feedback_received"


class ReactionType(str, Enum):
    like = "like"
    star = "star"
    heart = "heart"
    party = "party"
    muscle = "muscle"
    idea = "idea"


# ---------------------------------------------------------------------------
# Tables
# ---------------------------------------------------------------------------


class Tenant(Base):
    __tablename__ = "tenants"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    users: Mapped[list["TenantUser"]] = relationship("TenantUser", back_populates="tenant")
    projects: Mapped[list["Project"]] = relationship("Project", back_populates="tenant")


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    tenant_users: Mapped[list["TenantUser"]] = relationship(
        "TenantUser",
        foreign_keys="TenantUser.user_id",
        back_populates="user",
    )
    oauth_accounts: Mapped[list["OAuthAccount"]] = relationship(
        "OAuthAccount", back_populates="user"
    )
    tasks: Mapped[list["Task"]] = relationship("Task", back_populates="user")
    weekly_reports: Mapped[list["WeeklyReport"]] = relationship(
        "WeeklyReport", back_populates="user"
    )


class OAuthAccount(Base):
    __tablename__ = "oauth_accounts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    provider: Mapped[str] = mapped_column(String(50), nullable=False)
    provider_user_id: Mapped[str] = mapped_column(String(255), nullable=False)
    access_token: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    user: Mapped["User"] = relationship("User", back_populates="oauth_accounts")

    __table_args__ = (UniqueConstraint("provider", "provider_user_id"),)


class TenantUser(Base):
    __tablename__ = "tenant_users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    tenant_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    role: Mapped[str] = mapped_column(String(20), nullable=False, default=TenantUserRole.member)
    manager_user_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    tenant: Mapped["Tenant"] = relationship("Tenant", back_populates="users")
    user: Mapped["User"] = relationship(
        "User",
        foreign_keys="TenantUser.user_id",
        back_populates="tenant_users",
    )
    manager: Mapped["User | None"] = relationship(
        "User",
        foreign_keys="TenantUser.manager_user_id",
    )

    __table_args__ = (UniqueConstraint("tenant_id", "user_id"),)


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    tenant_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    color: Mapped[str] = mapped_column(String(20), nullable=False, default="#6366f1")
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    tenant: Mapped["Tenant"] = relationship("Tenant", back_populates="projects")
    members: Mapped[list["ProjectMember"]] = relationship(
        "ProjectMember", back_populates="project"
    )
    tasks: Mapped[list["Task"]] = relationship("Task", back_populates="project")


class ProjectMember(Base):
    __tablename__ = "project_members"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    project_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    project: Mapped["Project"] = relationship("Project", back_populates="members")
    user: Mapped["User"] = relationship("User")

    __table_args__ = (UniqueConstraint("project_id", "user_id"),)


class Task(Base):
    __tablename__ = "tasks"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    project_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("projects.id", ondelete="SET NULL"), nullable=True
    )
    name: Mapped[str] = mapped_column(String(500), nullable=False)
    estimated_hours: Mapped[float | None] = mapped_column(Float, nullable=True)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default=TaskStatus.todo
    )
    is_private: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    task_date: Mapped[str] = mapped_column(String(10), nullable=False)  # YYYY-MM-DD
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    user: Mapped["User"] = relationship("User", back_populates="tasks")
    project: Mapped["Project | None"] = relationship("Project", back_populates="tasks")


class WeeklyReport(Base):
    __tablename__ = "weekly_reports"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    week_start_date: Mapped[str] = mapped_column(String(10), nullable=False)  # YYYY-MM-DD (月曜日)
    ai_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    feeling: Mapped[str | None] = mapped_column(Text, nullable=True)
    questions: Mapped[str | None] = mapped_column(Text, nullable=True)
    issues: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(
        String(30), nullable=False, default=WeeklyReportStatus.draft
    )
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    feedback_seen_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    user: Mapped["User"] = relationship("User", back_populates="weekly_reports")
    feedbacks: Mapped[list["WeeklyReportFeedback"]] = relationship(
        "WeeklyReportFeedback", back_populates="report"
    )

    __table_args__ = (UniqueConstraint("user_id", "week_start_date"),)


class WeeklyReportFeedback(Base):
    __tablename__ = "weekly_report_feedbacks"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    report_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("weekly_reports.id", ondelete="CASCADE"), nullable=False
    )
    manager_user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    report: Mapped["WeeklyReport"] = relationship("WeeklyReport", back_populates="feedbacks")
    manager: Mapped["User"] = relationship("User")
    reactions: Mapped[list["WeeklyReportReaction"]] = relationship(
        "WeeklyReportReaction", back_populates="feedback"
    )


class WeeklyReportReaction(Base):
    __tablename__ = "weekly_report_reactions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    feedback_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("weekly_report_feedbacks.id", ondelete="CASCADE"), nullable=False
    )
    reaction_type: Mapped[str] = mapped_column(String(20), nullable=False)
    count: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    feedback: Mapped["WeeklyReportFeedback"] = relationship(
        "WeeklyReportFeedback", back_populates="reactions"
    )

    __table_args__ = (UniqueConstraint("feedback_id", "reaction_type"),)
