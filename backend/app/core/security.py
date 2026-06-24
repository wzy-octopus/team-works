from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import Depends, Header, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
bearer_scheme = HTTPBearer()


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def create_access_token(data: dict[str, Any], expires_delta: timedelta | None = None) -> str:
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    return jwt.encode({**data, "exp": expire}, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def decode_token(token: str) -> dict[str, Any]:
    try:
        return jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    except JWTError:
        return {}


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    x_tenant_id: str | None = Header(None, alias="X-Tenant-ID"),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """JWT を検証し、X-Tenant-ID ヘッダーでテナントを特定する。"""
    from app.models.models import TenantUser, User

    token = credentials.credentials
    payload = decode_token(token)

    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_id: str | None = payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token claims",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # tenant_id は X-Tenant-ID ヘッダー優先、なければ JWT の tenant_id を使用
    tenant_id: str | None = x_tenant_id or payload.get("tenant_id")
    if not tenant_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="X-Tenant-ID header is required",
        )

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")

    tu_result = await db.execute(
        select(TenantUser).where(
            TenantUser.user_id == user_id, TenantUser.tenant_id == tenant_id
        )
    )
    tenant_user = tu_result.scalar_one_or_none()
    if not tenant_user:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="User not in tenant"
        )

    return {
        "id": user.id,
        "email": user.email,
        "name": user.name,
        "role": tenant_user.role,
        "tenant_id": tenant_id,
        "manager_user_id": tenant_user.manager_user_id,
    }


async def resolve_user_context(
    token: str, db: AsyncSession, x_tenant_id: str | None = None
) -> dict[str, Any] | None:
    """JWT を検証しユーザーコンテキストを返す。無効なら None。

    get_current_user と同じ判定（署名・ユーザー存在・テナント所属）を、例外ではなく
    None で返す版。FastAPI の Depends を使えない箇所（MCP の ASGI 認証ゲート等）で使う。
    """
    from app.models.models import TenantUser, User

    payload = decode_token(token)
    if not payload:
        return None
    user_id = payload.get("sub")
    tenant_id = x_tenant_id or payload.get("tenant_id")
    if not user_id or not tenant_id:
        return None
    user = (await db.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
    if not user:
        return None
    tu = (
        await db.execute(
            select(TenantUser).where(
                TenantUser.user_id == user_id, TenantUser.tenant_id == tenant_id
            )
        )
    ).scalar_one_or_none()
    if not tu:
        return None
    return {
        "id": user.id,
        "email": user.email,
        "name": user.name,
        "role": tu.role,
        "tenant_id": tenant_id,
        "manager_user_id": tu.manager_user_id,
    }


async def require_admin(current_user: dict[str, Any] = Depends(get_current_user)) -> dict[str, Any]:
    if current_user["role"] != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin role required")
    return current_user
