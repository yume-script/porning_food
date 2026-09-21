import os

BASE_DIR = "/mnt/poring_food"
ENV_PATH = os.path.join(BASE_DIR, ".env")

ORG_PATH = os.path.join(BASE_DIR, "poring_food_organization.json")
ISSUE_PATH = os.path.join(BASE_DIR, "porting_food_issue.json")
PERSONA_PATH = os.path.join(BASE_DIR, "aesun_persona.json")

# [변경] 원래 os.path.join("/mnt/discord_bot", "aesun_current_status.json")였다 -
# discord_bot_v2 쪽 폴더에 파일을 쓰는 대신, 이제 완전히 독립된 개체로 두기 위해
# 자기 폴더 안에 저장한다. discord_bot_v2는 이 파일을 MCP 서버(mcp_server.py)를
# 통해서만 조회한다 - 직접 파일 경로를 공유하지 않는다.
STATUS_OUT_PATH = os.path.join(BASE_DIR, "aesun_current_status.json")

# [신규] 현재 상태 스냅샷만으로는 "어제 뭐 했어?" 같은 질문에 답할 수 없어서,
# 매 실행마다 누적 기록을 남기는 히스토리 로그. mcp_server.py의 get_recent_history()가 읽는다.
# 애순이뿐 아니라 다른 인물들의 기록도 character 필드로 구분해서 같은 파일에 쌓는다.
HISTORY_LOG_PATH = os.path.join(BASE_DIR, "aesun_history.jsonl")
HISTORY_RETENTION_DAYS = int(os.getenv("HISTORY_RETENTION_DAYS", "30"))

# [신규] 심시티처럼 인물 각자가 자기 상태/관계를 갖게 하는 다인물 시뮬레이션 관련 설정.
# ORGANIZATION_GLOB에 걸리는 파일은 전부 자동으로 "회사"로 인식된다 - 나중에 라이벌 회사가
# 늘어나도 "무슨무슨_organization.json" 파일 하나만 이 폴더에 추가하면 코드 수정 없이
# 자동으로 인식된다 (파일의 최상위 "company_name" 값을 회사명으로 쓴다).
ORGANIZATION_GLOB = os.path.join(BASE_DIR, "*_organization.json")
CHARACTERS_STATE_PATH = os.path.join(BASE_DIR, "characters_state.json")
RELATIONSHIPS_PATH = os.path.join(BASE_DIR, "relationships.json")
# 상호작용 이벤트를 만들 시각(하루 3번). .env의 INTERACTION_HOURS="10,15,20" 형식으로 조정 가능.
INTERACTION_HOURS = {
    int(h.strip()) for h in os.getenv("INTERACTION_HOURS", "10,15,20").split(",") if h.strip()
}

# [신규] "생산량"/"영업 판매수량"을 랜덤 대신 discord_bot_v2의 실제 대화 로그(SQLite)에서
# 가져온다 - 원래 지메일 API(OAuth)로 하려다, 이미 다른 프로젝트에서 OAuth 쿼터를 많이 쓰고
# 있고 게시 안 된 앱은 refresh_token이 7일마다 만료돼서 자동화에 안 맞아 포기했다. 이미
# 연동되어 있는 discord_bot_v2의 파일을 직접 읽는 쪽이 새 인증 없이 훨씬 간단하다.
DISCORD_BOT_V2_DB_PATH = os.getenv("DISCORD_BOT_V2_DB_PATH", "/mnt/discord_bot_v2/storage/conversations.db")


def load_env(filepath):
    env_vars = {}
    if not os.path.exists(filepath):
        return env_vars
    with open(filepath, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            env_vars[k.strip()] = v.strip()
    return env_vars


env = load_env(ENV_PATH)

DISCORD_WEBHOOK_URL = env.get("DISCORD_WEBHOOK_URL", os.getenv("DISCORD_WEBHOOK_URL"))
LOCAL_BOT_URL = env.get("LOCAL_BOT_URL", os.getenv("LOCAL_BOT_URL"))
ROOM_ID = env.get("ROOM_ID", os.getenv("ROOM_ID", "1234567890"))
ONE_API_URL = env.get("ONE_API_URL", os.getenv("ONE_API_URL"))
LITELLM_MASTER_KEY = env.get("LITELLM_MASTER_KEY", os.getenv("LITELLM_MASTER_KEY"))
LLM_MODEL = env.get("LLM_MODEL", os.getenv("LLM_MODEL", "gemini-free"))
SEARCH_MODEL = env.get("SEARCH_MODEL", os.getenv("SEARCH_MODEL", "gemini-search"))

# API Base URL 보정
API_URL = ""
if ONE_API_URL:
    base_url = ONE_API_URL.strip().rstrip("/")
    if not base_url.endswith("/v1") and not base_url.endswith("/v1/chat/completions"):
        API_URL = f"{base_url}/v1/chat/completions"
    elif base_url.endswith("/v1"):
        API_URL = f"{base_url}/chat/completions"
    else:
        API_URL = base_url
