from datetime import datetime

from pydantic import BaseModel


class WeeklyReportCreate(BaseModel):
    week_start_date: str
    feeling: str | None = None
    questions: str | None = None
    issues: str | None = None


class WeeklyReportUpdate(BaseModel):
    feeling: str | None = None
    questions: str | None = None
    issues: str | None = None


class WeeklyReportResponse(BaseModel):
    id: str
    user_id: str
    week_start_date: str
    ai_summary: str | None
    feeling: str | None
    questions: str | None
    issues: str | None
    status: str
    submitted_at: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}


class InboxReportResponse(WeeklyReportResponse):
    user_name: str
    user_email: str


class FeedbackCreate(BaseModel):
    comment: str | None = None
    reaction_types: list[str] = []


class FeedbackResponse(BaseModel):
    id: str
    manager_user_id: str
    comment: str | None
    reactions: list[str]
    created_at: datetime

    model_config = {"from_attributes": True}
