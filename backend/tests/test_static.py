"""静的ファイル配信のテスト。

ルート直下の実ファイル（favicon.svg 等）が SPA の index.html に飲み込まれず、
実体を返すことを確認する。実ファイルの無いパスは index.html にフォールバックする。
"""

import pytest
from httpx import AsyncClient

from app.main import STATIC_DIR


@pytest.mark.asyncio
async def test_favicon_served_as_file(alice_client: AsyncClient) -> None:
    """/favicon.svg は実ファイル（SVG）を返し、index.html にならない。"""
    if not (STATIC_DIR / "favicon.svg").is_file():
        pytest.skip("favicon.svg がビルド成果物に存在しない")
    resp = await alice_client.get("/favicon.svg")
    assert resp.status_code == 200
    assert "svg" in resp.headers.get("content-type", "").lower()
    assert 'id="root"' not in resp.text  # SPA の index.html ではない


@pytest.mark.asyncio
async def test_client_route_falls_back_to_index(alice_client: AsyncClient) -> None:
    """実ファイルの無いパス（クライアントルート）は index.html を返す。"""
    if not (STATIC_DIR / "index.html").is_file():
        pytest.skip("index.html がビルド成果物に存在しない")
    resp = await alice_client.get("/some/client/route")
    assert resp.status_code == 200
    assert 'id="root"' in resp.text
