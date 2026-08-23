import os

BASE_DIR = "/mnt/poring_food"
ENV_PATH = os.path.join(BASE_DIR, ".env")
ORG_PATH = os.path.join(BASE_DIR, "poring_food_organization.json")
ISSUE_PATH = os.path.join(BASE_DIR, "porting_food_issue.json")
PERSONA_PATH = os.path.join(BASE_DIR, "aesun_persona.json")
STATUS_OUT_PATH = os.path.join("/mnt/discord_bot", "aesun_current_status.json")

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

