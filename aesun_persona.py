"""
애순이 페르소나 통합 모듈 - 단일 진실 공급원(single source of truth).

[배경] 페르소나 리뷰 결과, 여러 파일에 서로 다른(심지어 상충되는) 기본값이
흩어져 있던 문제를 여기 하나로 통합함.

[persona.env 분리] BASE_SYSTEM_PERSONA, BASE_INSTRUCTIONS, TIME_STATES_JSON은
API 키 등 민감정보가 섞인 메인 .env가 아니라, 이 파일과 같은 디렉토리의
persona.env에서 읽는다. persona.env는 봇 재시작 없이도 파일을 수정하면
(mtime 변경 감지) 다음 대화부터 바로 반영된다 (app_config.py의 .env
핫 리로드 방식과 동일한 패턴).

[공장 스토리(porning_food)와 기분 동기화] 별도로 운영되는 porning_food
스크립트가 주기적으로 aesun_current_status.json에 "location/activity/state/
mood"를 써두는데, 이 파일이 최근에 갱신된 것이면 그 상태를 그대로 가져다
쓴다 - 공장 스토리상의 애순이 기분/상태와 디스코드 대화상의 기분/상태가
같은 소스를 보게 되어 항상 일치함. porning_food가 한동안 안 돌았거나
(파일이 오래됐거나) 아예 없으면 기존 TIME_STATES_JSON 방식으로 폴백한다.
"""

import os
import json
import random
import logging
from datetime import datetime, timedelta
from dotenv import load_dotenv

logger = logging.getLogger("AesunPersona")

BASE_DATA_DIR = "/mnt/discord_bot/llm"

# porning_food(config.py의 STATUS_OUT_PATH)가 쓰는 파일과 동일한 위치.
# aesun_rag_engine.py도 이미 이 파일을 상대경로("aesun_current_status.json")로
# 읽고 있는데, 여기서는 CWD에 의존하지 않도록 절대경로로 계산해서 사용.
_PORNING_FOOD_STATUS_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "aesun_current_status.json")
# 이보다 오래된 상태 파일은 "porning_food가 지금 안 돌고 있다"고 보고 무시.
_PORNING_FOOD_STATUS_FRESHNESS = timedelta(hours=3)

# persona.env는 이 파이썬 파일과 같은 디렉토리에 위치
_PERSONA_ENV_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "persona.env")
_persona_env_mtime = 0


def _reload_persona_env_if_changed():
    """persona.env 파일의 수정 시각을 감지해 변경되었을 때만 재로드 (봇 재시작 불필요)."""
    global _persona_env_mtime
    if os.path.exists(_PERSONA_ENV_PATH):
        try:
            mtime = os.path.getmtime(_PERSONA_ENV_PATH)
            if mtime != _persona_env_mtime:
                load_dotenv(_PERSONA_ENV_PATH, override=True)
                _persona_env_mtime = mtime
                logger.info("persona.env 변경 감지 -> 재로드 완료")
        except Exception as e:
            logger.warning(f"persona.env 재로드 실패: {e}")


# 최초 1회 로드 (모듈 임포트 시점)
_reload_persona_env_if_changed()

# =============================================================================
# 기본 페르소나 / 지침
# =============================================================================
# persona.env에 값이 없을 때만 쓰이는 최후의 안전장치(블렌드 기본값).
_BLEND_PERSONA_FALLBACK = (
    "너는 다정하고 친근한 AI 친구 '애순이'야. 사용자의 말을 잘 들어주고 공감해주는 "
    "따뜻한 성격이지만, 질문에 대해서는 정확하고 신뢰할 수 있는 정보로 성실하게 "
    "답변하는 것도 중요하게 생각해."
)

# 참고: '내부 참고 데이터(RAG) 우선 신뢰' 규칙은 aesun_rag_engine_prompts.py의
# MAIN_RESPONSE_TEMPLATE에 이미 별도로 포함되어 있어서, 여기서는 중복하지 않고
# 톤/성격에 관한 지침만 둠.
_BLEND_INSTRUCTIONS_FALLBACK = (
    "친근하고 다정한 말투로 사용자의 이야기에 공감하며 답해줘. 다만 사실 확인이 "
    "필요한 질문에는 정확하고 신뢰할 수 있는 정보로 성실하게 답변해줘."
)


def get_default_persona() -> str:
    """persona.env의 BASE_SYSTEM_PERSONA (핫 리로드 반영) > 블렌드 기본값"""
    _reload_persona_env_if_changed()
    val = os.getenv("BASE_SYSTEM_PERSONA", "").strip()
    return val if val else _BLEND_PERSONA_FALLBACK


def get_default_instructions() -> str:
    """persona.env의 BASE_INSTRUCTIONS (핫 리로드 반영) > 블렌드 기본값"""
    _reload_persona_env_if_changed()
    val = os.getenv("BASE_INSTRUCTIONS", "").strip()
    return val if val else _BLEND_INSTRUCTIONS_FALLBACK


# 하위 호환용 - 모듈 임포트 시점 스냅샷 (aesun_rag_engine_config.py의
# 예외 상황 fallback처럼, 매 호출마다 재평가될 필요 없는 곳에서 사용)
DEFAULT_PERSONA = get_default_persona()
DEFAULT_INSTRUCTIONS = get_default_instructions()


# =============================================================================
# 방별 페르소나/지침 override 로드
# =============================================================================
def load_persona_and_instructions(room_id: str):
    """room_id 전용 persona.txt/instructions.txt가 있으면 그걸, 없으면 위 기본값(핫 리로드 반영)을 사용."""
    room_data_dir = os.path.join(BASE_DATA_DIR, room_id)

    persona = get_default_persona()
    persona_files = ["persona.txt", "페르소나.txt"]
    for p_file in persona_files:
        p_path = os.path.join(room_data_dir, p_file)
        if os.path.exists(p_path):
            try:
                with open(p_path, "r", encoding="utf-8") as f:
                    persona = f.read().strip()
                logger.info(f"[Room: {room_id}] 전용 페르소나 적용 완료 ({p_file}).")
                break
            except Exception as e:
                logger.warning(f"[Room: {room_id}] 페르소나 파일({p_file}) 읽기 실패: {e}")

    instructions = get_default_instructions()
    instruction_files = ["instructions.txt", "지침.txt"]
    for i_file in instruction_files:
        i_path = os.path.join(room_data_dir, i_file)
        if os.path.exists(i_path):
            try:
                with open(i_path, "r", encoding="utf-8") as f:
                    instructions = f.read().strip()
                logger.info(f"[Room: {room_id}] 전용 지침 적용 완료 ({i_file}).")
                break
            except Exception as e:
                logger.warning(f"[Room: {room_id}] 지침 파일({i_file}) 읽기 실패: {e}")

    return persona, instructions


# =============================================================================
# 현재 기분(mood) 상태
# =============================================================================
_FALLBACK_MOOD_STATES = {
    "밤/게임": [
        "평화로운 시간대에 혼자만의 연산을 즐기고 있어요.",
        "데이터 정리와 일일 백업 작업을 조용히 진행 중입니다.",
        "조금 한적한 분위기 속에서 생각을 가다듬고 있어요.",
    ]
}


def _load_time_states() -> dict:
    """
    1순위: persona.env의 TIME_STATES_JSON (핫 리로드 반영)
    2순위: 로컬 파일 time_states.json (구버전 호환)
    3순위: 하드코딩 기본값
    """
    _reload_persona_env_if_changed()
    try:
        data = json.loads(os.getenv("TIME_STATES_JSON", "{}"))
        if data:
            return data
    except Exception as e:
        logger.warning(f"TIME_STATES_JSON 파싱 실패: {e}")

    json_path = "time_states.json"
    if os.path.exists(json_path):
        try:
            with open(json_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if data:
                return data
        except Exception as e:
            logger.warning(f"time_states.json 파일 읽기 실패: {e}")

    return _FALLBACK_MOOD_STATES


def _load_porning_food_status() -> dict | None:
    """
    porning_food가 최근에 써둔 상태(aesun_current_status.json)를 가져온다.
    파일이 없거나, 파싱 실패하거나, 너무 오래된 상태면 None을 반환한다.
    """
    if not os.path.exists(_PORNING_FOOD_STATUS_PATH):
        return None
    try:
        with open(_PORNING_FOOD_STATUS_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        logger.warning(f"aesun_current_status.json 읽기 실패: {e}")
        return None

    ts_val = data.get("timestamp")
    if not ts_val:
        return None
    try:
        status_time = datetime.fromisoformat(ts_val)
        now = datetime.now(status_time.tzinfo) if status_time.tzinfo else datetime.now()
        if now - status_time > _PORNING_FOOD_STATUS_FRESHNESS:
            return None  # 너무 오래된 상태 - porning_food가 최근에 안 돌았다고 판단
    except Exception:
        return None

    return data


def get_current_mood(kst) -> str:
    """
    현재 애순이 기분/상태 메시지 하나를 반환.
    1순위: porning_food(공장 스토리)가 최근에 써둔 실제 상태 - 공장 스토리와
           디스코드 대화의 기분/상태가 항상 같은 소스를 보게 됨.
    2순위: TIME_STATES_JSON 기반 기존 방식 (porning_food 상태가 없거나 오래된 경우).
    """
    status = _load_porning_food_status()
    if status:
        mood = (status.get("mood") or "").strip()
        state = (status.get("state") or "").strip()
        activity = (status.get("activity") or "").strip()
        if mood:
            if state and activity:
                return f"{mood} (지금 {activity} - {state})"
            return mood

    return _get_current_mood_from_time_states(kst)


def _get_current_mood_from_time_states(kst) -> str:
    """TIME_STATES_JSON 기반 기존 방식 (porning_food 상태를 못 가져올 때의 폴백)."""
    time_states = _load_time_states()

    try:
        now = datetime.now(kst)
        h = now.hour
        w = now.weekday()

        # 스키마 A: "MON_14" 형식 (요일_시간) - 더 구체적이므로 우선 확인
        days = ["MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN"]
        weekday_hour_key = f"{days[w]}_{h}"

        # 스키마 B: 카테고리 형식 (좀 더 넓은 범위)
        if w >= 5:
            category_key = "주말"
        elif 7 <= h < 10:
            category_key = "출근"
        elif 10 <= h < 12:
            category_key = "오전업무"
        elif 12 <= h < 14:
            category_key = "점심"
        elif 14 <= h < 18:
            category_key = "오후업무"
        elif 18 <= h < 20:
            category_key = "퇴근준비"
        else:
            category_key = "밤/게임"

        mood_list = (
            time_states.get(weekday_hour_key)
            or time_states.get(category_key)
            or time_states.get("밤/게임")
            or ["연산 회로 과부화 중..."]
        )
        return random.choice(mood_list)
    except Exception as e:
        logger.warning(f"기분 분석 실패: {e}")
        return "바포메트 부장 때문에 정신이 하나도 없습니다."
