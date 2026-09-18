"""
포링푸드(애순이)를 discord_bot_v2(아메하나)에게 MCP 서버로 노출한다.
discord_bot_v2가 SSH+docker exec로 BookOasis MCP 서버에 접속하는 것과 같은 패턴인데,
포링푸드는 같은 서버("etc")에서 도니까 SSH 없이 discord_bot_v2가 바로
"python3 /mnt/poring_food/mcp_server.py"로 이 파일을 stdio로 실행한다.

설치: pip install mcp

이 파일을 추가하면서 config.py의 STATUS_OUT_PATH도 포링푸드 자기 폴더 안으로 옮겼다 -
더 이상 discord_bot_v2 쪽 폴더에 아무것도 쓰지 않는다. 완전히 독립된 개체로 두고,
discord_bot_v2는 이 MCP 서버를 통해서만 상태를 물어본다.
"""
from __future__ import annotations

import json
import os

from mcp.server.fastmcp import FastMCP

from config import STATUS_OUT_PATH

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


if __name__ == "__main__":
    mcp.run()  # 기본 transport가 stdio
