from app.core.config import settings

_STATUS_JA = {"todo": "未着手", "in_progress": "進行中", "done": "完了"}

_SYSTEM_PROMPT = """あなたはチームマネジメントの専門家です。
メンバーの週次タスクデータを分析し、簡潔かつ建設的な週報サマリを日本語で生成してください。
200〜400字程度でまとめ、今週の成果・進捗・課題を整理してください。"""


def _make_client():
    """LLM_BACKEND 設定に応じてクライアントとモデル名を返す。"""
    if settings.LLM_BACKEND == "foundry" and settings.FOUNDRY_API_KEY and settings.FOUNDRY_ENDPOINT:
        from anthropic import AnthropicFoundry  # type: ignore
        return AnthropicFoundry(api_key=settings.FOUNDRY_API_KEY, base_url=settings.FOUNDRY_ENDPOINT), settings.FOUNDRY_MODEL
    else:
        from anthropic import Anthropic
        return Anthropic(api_key=settings.ANTHROPIC_API_KEY), "claude-sonnet-4-5"


def generate_weekly_summary(week_start_date: str, user_name: str, tasks: list[dict]) -> str:
    """週次タスク一覧から AI サマリを生成して返す（同期関数）。"""
    client, model = _make_client()

    if tasks:
        lines = []
        for t in tasks:
            status_ja = _STATUS_JA.get(t["status"], t["status"])
            line = f"- [{status_ja}] {t['name']}"
            if t.get("estimated_hours"):
                line += f"（見積 {t['estimated_hours']}h）"
            lines.append(line)
        task_text = "\n".join(lines)
    else:
        task_text = "（公開タスクなし）"

    user_prompt = (
        f"{user_name} さんの {week_start_date} 週（月曜始まり）のタスク一覧:\n\n"
        f"{task_text}\n\n"
        "この内容をもとに週報サマリを日本語で作成してください。"
    )

    response = client.messages.create(
        model=model,
        max_tokens=1024,
        system=_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_prompt}],
    )

    return response.content[0].text
