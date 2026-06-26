"""MCP ツールの整形ロジックのテスト（純関数）。"""

from app.mcp_app import _format_team_dashboard


def test_format_team_dashboard_groups_members_and_hides_private_content() -> None:
    data = {
        "tasks": [
            {
                "user_id": "u1", "user_name": "Alice", "project_name": "AX本部",
                "name": "設計", "status": "done", "estimated_hours": 2, "is_private": False,
            },
            {
                "user_id": "u1", "user_name": "Alice", "project_name": "AX本部",
                "name": "実装", "status": "in_progress", "estimated_hours": None, "is_private": True,
            },
            {
                "user_id": "u2", "user_name": "Bob", "project_name": "AX本部",
                "name": "レビュー", "status": "todo", "estimated_hours": 1, "is_private": False,
            },
        ],
        "private_counts": {"u2": 3},
        "past_incomplete_summary": {"total": 0, "items": []},
    }
    out = _format_team_dashboard(data, "pid", "2026-06-26")

    # メンバーごとにグルーピングされ、両者が出る
    assert "Alice" in out
    assert "Bob" in out
    # 公開タスクの中身は出る
    assert "設計" in out
    assert "レビュー" in out
    # プロジェクト名・日付が出る
    assert "AX本部" in out
    assert "2026-06-26" in out
    # 他メンバーの非公開はタスク名を出さず件数のみ
    assert "🔒 非表示 3件" in out


def test_format_team_dashboard_empty() -> None:
    data = {"tasks": [], "private_counts": {}, "past_incomplete_summary": {"total": 0, "items": []}}
    out = _format_team_dashboard(data, "pid", "2026-06-26")
    assert "2026-06-26" in out
