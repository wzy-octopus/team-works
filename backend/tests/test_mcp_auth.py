"""MCP 用トークン発行と /mcp 認証ゲートのテスト。"""

from datetime import datetime, timezone

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.security import decode_token
from app.main import app


@pytest.mark.asyncio
async def test_mcp_token_is_long_lived(alice_client: AsyncClient) -> None:
    resp = await alice_client.post("/api/auth/mcp-token")
    assert resp.status_code == 200
    token = resp.json()["access_token"]
    payload = decode_token(token)
    assert payload  # decodes
    exp = datetime.fromtimestamp(payload["exp"], tz=timezone.utc)
    # 90 日より先（長期トークン）であること
    assert (exp - datetime.now(timezone.utc)).days > 90


@pytest.mark.asyncio
async def test_mcp_requires_token() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        resp = await c.post("/mcp", json={"jsonrpc": "2.0", "id": 1, "method": "ping"})
    assert resp.status_code == 401
