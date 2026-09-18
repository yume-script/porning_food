"""
포링푸드(애순이)를 discord_bot_v2(아메하나)에게 MCP 서버로 노출한다.
discord_bot_v2가 SSH+docker exec로 BookOasis MCP 서버에 접속하는 것과 같은 패턴인데,
포링푸드는 같은 서버("etc")에서 도니까 SSH 없이 discord_bot_v2가 바로
"python3 /mnt/poring_food/mcp_server.py"로 이 파일을 stdio로 실행한다.

설치: pip install mcp

config.py의 STATUS_OUT_PATH/HISTORY_LOG_PATH 둘 다 포링푸드 자기 폴더 안에 있다 -
discord_bot_v2 쪽 폴더에는 아무것도 안 쓴다. 완전히 독립된 개체로 두고,
discord_bot_v2는 이 MCP 서버를 통해서만 상태/히스토리를 물어본다.

get_recent_history()는 "어제 뭐 했어?" 같은 질문에 답하기 위해 추가한 도구다 -
notifier.append_to_history()가 매 실행마다 쌓아둔 aesun_history.jsonl을 읽는다.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timedelta

from mcp.server.fastmcp import FastMCP

from config import STATUS_OUT_PATH, HISTORY_LOG_PATH

mcp = FastMCP("poring-food")


@mcp.tool()
def get_current_status() -> str:
    """애순이(포링푸드 공장)의 현재 상태와 하고 있는 활동을 알려준다."""
    if not os.path.exists(STATUS_OUT_PATH):
        return "아직 상태 정보가 없어요 (첫 실행 전이거나 파일이 없음)."

    try:
        with open(STATUS_OUT_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        return f"상태 파일을 읽는 중 오류가 발생했어요: {e}"

    parts = []
    if data.get("time_tag"):
        parts.append(f"[{data['time_tag']}]")
    if data.get("location") and data.get("activity"):
        parts.append(f"애순이는 지금 {data['location']}에서 {data['activity']} 중이에요.")
    elif data.get("activity"):
        parts.append(f"애순이는 지금 {data['activity']} 중이에요.")
    if data.get("state"):
        parts.append(f"(상태: {data['state']})")
    if data.get("mood"):
        parts.append(f"오늘 기분: {data['mood']}.")

    narrative = data.get("narrative") or data.get("full_report")
    if narrative:
        parts.append(str(narrative))

    return " ".join(parts) if parts else "상태 데이터는 있는데 읽을 수 있는 내용이 없어요."


@mcp.tool()
def get_recent_history(days: int = 1) -> str:
    """
    애순이가 최근에 뭘 했는지 알려준다. "어제 뭐 했어?"는 days=1, "요즘/최근 며칠 뭐 했어?"는
    days=3~7 정도로 호출하면 된다. 하루에 여러 번(시간대별) 기록이 쌓이기 때문에, 하루당
    대표로 3개(오전/오후/저녁 근처)까지만 골라서 너무 길어지지 않게 요약한다.
    """
    if not os.path.exists(HISTORY_LOG_PATH):
        return "아직 히스토리 기록이 없어요."

    try:
        entries = []
        with open(HISTORY_LOG_PATH, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entries.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    except OSError as e:
        return f"히스토리 파일을 읽는 중 오류가 발생했어요: {e}"

    if not entries:
        return "히스토리 기록이 비어있어요."

    cutoff = datetime.now() - timedelta(days=days)
    by_date: dict[str, list[dict]] = {}
    for e in entries:
        ts = e.get("timestamp")
        if not ts:
            continue
        try:
            dt = datetime.fromisoformat(ts)
        except ValueError:
            continue
        if dt < cutoff:
            continue
        date_key = dt.strftime("%Y-%m-%d")
        by_date.setdefault(date_key, []).append(e)

    if not by_date:
        return f"최근 {days}일 동안의 기록이 없어요."

    lines = []
    for date_key in sorted(by_date.keys()):
        day_entries = by_date[date_key]
        # 하루에 너무 많이 쌓이니 대표로 최대 3개만 (앞/중간/끝)
        picks = day_entries if len(day_entries) <= 3 else [
            day_entries[0], day_entries[len(day_entries) // 2], day_entries[-1]
        ]
        day_lines = []
        for e in picks:
            tag = e.get("time_tag", "")
            act = e.get("activity", "")
            loc = e.get("location", "")
            if act:
                day_lines.append(f"{tag} {loc}에서 {act}" if loc else f"{tag} {act}")
        if day_lines:
            lines.append(f"[{date_key}] " + " / ".join(day_lines))

    return "\n".join(lines) if lines else f"최근 {days}일 동안의 기록이 없어요."


if __name__ == "__main__":
    mcp.run()  # 기본 transport가 stdio
