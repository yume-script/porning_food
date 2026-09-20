"""
포링푸드(애순이와 동료들)를 discord_bot_v2(아메하나)에게 MCP 서버로 노출한다.
discord_bot_v2가 SSH+docker exec로 BookOasis MCP 서버에 접속하는 것과 같은 패턴인데,
포링푸드는 같은 서버("etc")에서 도니까 SSH 없이 discord_bot_v2가 바로
"python3 /mnt/poring_food/mcp_server.py"로 이 파일을 stdio로 실행한다.

설치: pip install mcp

config.py의 STATUS_OUT_PATH/HISTORY_LOG_PATH/CHARACTERS_STATE_PATH 전부 포링푸드 자기
폴더 안에 있다 - discord_bot_v2 쪽 폴더에는 아무것도 안 쓴다.

[확장] 원래 애순이 전용이었는데, 심시티처럼 다른 인물들도 각자 상태/기록을 갖게 되면서
character 파라미터로 아무나 조회할 수 있게 넓혔다(기본값은 "애순이"라 기존 사용법은
그대로 작동한다). get_character_list()로 누가 있는지부터 물어볼 수도 있다.
get_all_characters_status()로 전원의 현재 위치/활동을 한 번에 볼 수도 있다.

[신규] 매시 방송(스포트라이트)은 애순이와 다른 26명 중 가중치 랜덤으로 한 명에게만
돌아간다(main.py의 로테이션) - 방송 안 된 인물의 근황이 궁금하면 get_character_story()가
그 자리에서 즉석으로 짧은 이야기를 만들어준다(같은 시간대 안에서는 캐시 재사용).
"""
import glob
import json
import os
from datetime import datetime, timedelta

from mcp.server.fastmcp import FastMCP

from config import STATUS_OUT_PATH, HISTORY_LOG_PATH, CHARACTERS_STATE_PATH, ORGANIZATION_GLOB
import characters
import processor
import generator

mcp = FastMCP("poring-food")

# [신규] 온디맨드 이야기 캐시 - 같은 시간대(시 단위) 안에서 같은 인물을 여러 번 물어봐도
# LLM을 다시 호출하지 않는다. 이 서버는 discord_bot_v2가 부팅할 때 한 번 실행되어 계속
# 떠있는 프로세스라(매 호출마다 새로 뜨는 게 아님), 이 캐시가 프로세스 수명 동안 유지된다.
_story_cache: dict[tuple[str, str], str] = {}


def _load_characters_state() -> dict:
    if not os.path.exists(CHARACTERS_STATE_PATH):
        return {}
    try:
        with open(CHARACTERS_STATE_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}


def _find_state_by_name(name: str) -> list[tuple[str, dict]]:
    """이름으로 상태를 찾는다. 이름이 겹치는 인물(예: 미믹)이 있으면 여러 개가 나올 수 있다."""
    states = _load_characters_state()
    return [(cid, info) for cid, info in states.items() if info.get("name") == name]


@mcp.tool()
def get_current_status(character: str = "애순이") -> str:
    """
    한 인물의 현재 상태와 하고 있는 활동을 알려준다. character를 생략하면 애순이를 조회한다.
    애순이는 매시 LLM이 작성한 상세한 근황(기분/이야기 포함)까지 나오고, 다른 인물은
    위치/활동/소속 정도의 간단한 정보만 나온다. 누가 있는지 모르면 get_character_list를 먼저 써라.
    """
    if character == "애순이":
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

    matches = _find_state_by_name(character)
    if not matches:
        return f"'{character}'라는 인물을 못 찾았어요. get_character_list로 누가 있는지 확인해보세요."

    if len(matches) > 1:
        lines = [f"'{character}'라는 이름이 여러 회사에 있어요:"]
        for cid, info in matches:
            lines.append(f"- {info.get('company')}: {info.get('location')}에서 {info.get('activity')} 중")
        return "\n".join(lines)

    _, info = matches[0]
    parts = [f"{character}({info.get('company')} {info.get('dept')})는 지금"]
    if info.get("location") and info.get("activity"):
        parts.append(f"{info['location']}에서 {info['activity']} 중이에요.")
    elif info.get("activity"):
        parts.append(f"{info['activity']} 중이에요.")
    if info.get("state"):
        parts.append(f"(상태: {info['state']})")
    narrative = info.get("narrative")
    if narrative:
        parts.append(str(narrative))
    return " ".join(parts)


@mcp.tool()
def get_character_list() -> str:
    """포링푸드와 라이벌 회사에 등장하는 인물 전체 목록(이름/회사/부서/직급)을 알려준다."""
    entries = []
    for path in sorted(glob.glob(ORGANIZATION_GLOB)):
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            continue
        company = data.get("company_name", os.path.basename(path))
        for dept in data.get("departments", []):
            for m in dept.get("members", []):
                entries.append(f"- {m['name']} ({company} {dept.get('dept_name', '')} {m.get('rank', '')})")
    if not entries:
        return "조직도를 못 읽었어요."
    return "\n".join(entries)


@mcp.tool()
def get_recent_history(character: str = "애순이", days: int = 1) -> str:
    """
    한 인물이 최근에 뭘 했는지 알려준다. character를 생략하면 애순이 기록을 본다.
    "어제 뭐 했어?"는 days=1, "요즘/최근 며칠 뭐 했어?"는 days=3~7 정도로 호출하면 된다.
    하루에 여러 번(시간대별) 기록이 쌓이기 때문에, 하루당 대표로 3개까지만 골라서
    너무 길어지지 않게 요약한다.
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
                    e = json.loads(line)
                except json.JSONDecodeError:
                    continue
                # character 필드가 없는(옛날 형식) 줄은 애순이 기록으로 간주 - 하위 호환.
                if e.get("character", "애순이") == character:
                    entries.append(e)
    except OSError as e:
        return f"히스토리 파일을 읽는 중 오류가 발생했어요: {e}"

    if not entries:
        return f"'{character}'의 히스토리 기록이 없어요."

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
            piece = f"{tag} {loc}에서 {act}" if loc else f"{tag} {act}"
            if e.get("narrative"):
                piece += f" ({e['narrative']})"
            if act:
                day_lines.append(piece)
        if day_lines:
            lines.append(f"[{date_key}] " + " / ".join(day_lines))

    return "\n".join(lines) if lines else f"최근 {days}일 동안의 기록이 없어요."


@mcp.tool()
def get_all_characters_status() -> str:
    """
    포링푸드와 라이벌 회사 전원(애순이 포함)이 지금 각자 어디서 뭘 하고 있는지 한 번에
    보여준다. "포링푸드 사람들 지금 뭐하고 있지?", "다들 뭐해?" 같은 전체 근황 질문에 쓴다.
    회사별로 묶어서 보여준다.
    """
    states = _load_characters_state()
    if not states:
        return "아직 상태 정보가 없어요 (첫 실행 전이거나 파일이 없음)."

    by_company: dict[str, list[str]] = {}
    for info in states.values():
        name = info.get("name", "?")
        location = info.get("location", "")
        activity = info.get("activity", "")
        company = info.get("company", "기타")
        if location and activity:
            line = f"{name}: {location}에서 {activity}"
        elif activity:
            line = f"{name}: {activity}"
        else:
            line = f"{name}: 상태 정보 없음"
        by_company.setdefault(company, []).append(line)

    blocks = []
    for company in sorted(by_company.keys()):
        lines = "\n".join(f"- {l}" for l in by_company[company])
        blocks.append(f"【{company}】\n{lines}")
    return "\n\n".join(blocks)


@mcp.tool()
def get_character_story(character: str) -> str:
    """
    [신규] 스포트라이트(매시 1명 방송) 순서가 안 돌아온 인물이 지금 뭘 하고 있는지, 그 사람
    시점의 짧은 이야기를 그 자리에서 즉석으로 만들어 알려준다. "오크히어로 오늘 뭐해?"처럼
    누군가의 근황이 궁금할 때 쓴다. 애순이는 get_current_status("애순이")가 이미 상세하게
    답하니 이 도구는 애순이 외의 인물에 쓴다. 같은 시간대 안에서는 캐시된 결과를 재사용해서
    똑같은 사람을 여러 번 물어봐도 LLM을 다시 호출하지 않는다.
    """
    if character == "애순이":
        return get_current_status("애순이")

    cache_key = (character, datetime.now().strftime("%Y-%m-%d-%H"))
    if cache_key in _story_cache:
        return _story_cache[cache_key]

    matches = _find_state_by_name(character)
    if not matches:
        result = f"'{character}'라는 인물을 못 찾았어요. get_character_list로 누가 있는지 확인해보세요."
        _story_cache[cache_key] = result
        return result
    if len(matches) > 1:
        return f"'{character}'라는 이름이 여러 회사에 있어요 - 어느 회사인지 알려주시면 좁혀드릴게요."

    _, info = matches[0]
    if info.get("state") == "자는 중":
        result = f"{character}는 지금 자고 있어서 이야기를 만들 수가 없어요. 나중에 다시 물어봐주세요."
        _story_cache[cache_key] = result
        return result

    persona = None
    for c in characters.load_roster():
        if c["name"] == character and c["company"] == info.get("company"):
            persona = c
            break
    if not persona:
        result = f"'{character}'의 페르소나 정보를 조직도에서 못 찾았어요."
        _story_cache[cache_key] = result
        return result

    issue = processor.get_last_issue() or {"title": "평범한 하루", "description": "특별한 일 없는 하루"}
    mood = processor.get_daily_mood()

    try:
        report = generator.generate_generic_character_report(
            persona, issue, processor.get_time_tag(), "정보 없음", mood,
            info.get("location", ""), info.get("activity", ""), info.get("state", ""),
        )
        result = report.get("narrative", "") or "이야기를 만들었는데 내용이 비어있어요."
    except Exception as e:
        result = f"{character}의 이야기를 만드는 중 오류가 발생했어요: {e}"

    _story_cache[cache_key] = result
    return result


if __name__ == "__main__":
    mcp.run()  # 기본 transport가 stdio
