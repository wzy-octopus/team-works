from datetime import datetime

from pydantic import BaseModel


class TaskCreate(BaseModel):
    name: str
    estimated_hours: float | None = None
    project_id: str | None = None
    is_private: bool = False
    task_date: str  # YYYY-MM-DD


class TaskUpdate(BaseModel):
    name: str | None = None
    estimated_hours: float | None = None
    status: str | None = None
    is_private: bool | None = None


class TaskResponse(BaseModel):
    id: str
    name: str
    estimated_hours: float | None
    status: str
    is_private: bool
    task_date: str
    project_id: str | None
    user_id: str
    created_at: datetime

    model_config = {"from_attributes": True}


class TaskListResponse(BaseModel):
    tasks: list[TaskResponse]
