from datetime import datetime

from pydantic import BaseModel


class TenantUserUpdate(BaseModel):
    role: str | None = None
    manager_user_id: str | None = None
    clear_manager: bool = False  # manager_user_id を NULL にするための明示フラグ


class ProjectCreate(BaseModel):
    name: str
    color: str = "#6366f1"
    description: str | None = None


class ProjectResponse(BaseModel):
    id: str
    name: str
    color: str
    description: str | None
    member_count: int = 0

    model_config = {"from_attributes": True}


class MemberResponse(BaseModel):
    id: str        # TenantUser.id
    user_id: str   # User.id
    name: str
    email: str
    role: str
    manager_user_id: str | None
    project_ids: list[str]
    last_login_at: datetime | None

    model_config = {"from_attributes": True}


class InviteRequest(BaseModel):
    email: str
    role: str = "member"
    name: str | None = None
