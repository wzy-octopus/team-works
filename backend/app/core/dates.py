"""業務日付ユーティリティ。

タスクの `task_date` などの「業務日付」は、サーバー/DB のタイムゾーン（Azure では UTC）
ではなく日本時間 JST(+09:00) を基準に算出する。DB 全体のタイムゾーンは変更しない。
"""

from datetime import datetime, timedelta, timezone

JST = timezone(timedelta(hours=9))


def business_today() -> str:
    """JST(+09:00) の業務日付を YYYY-MM-DD で返す。"""
    return datetime.now(JST).date().isoformat()
