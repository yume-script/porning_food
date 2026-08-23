import random
import requests
import json
import os
from datetime import datetime, timedelta
from dotenv import load_dotenv
from config import API_URL, LITELLM_MASTER_KEY, LLM_MODEL, SEARCH_MODEL

# .env 로드
load_dotenv()

ISSUE_LOG_FILE = "last_issue.json"
LOG_FILE_PATH = "/mnt/discord_bot/katalk_log/log_18221226698539974.jsonl"
DAILY_TARGET = int(os.getenv("DAILY_TARGET_PRODUCTION", 1000))

def get_production_stats():
    """오늘 날짜의 메시지 로그 수를 계산하여 진행률 반환"""
    today_str = datetime.now().strftime("%Y-%m-%d")
    count = 0
    
    try:
        if os.path.exists(LOG_FILE_PATH):
            with open(LOG_FILE_PATH, "r", encoding="utf-8") as f:
                for line in f:
                    if not line.strip(): continue
                    try:
                        entry = json.loads(line)
                        timestamp_str = entry.get("timestamp", "")
                        if timestamp_str.startswith(today_str):
                            count += 1
                    except json.JSONDecodeError:
                        continue
    except Exception as e:
        print(f"[경고] 로그 분석 중 오류 발생: {e}")
    
    progress = (count / DAILY_TARGET) * 100 if DAILY_TARGET > 0 else 0
    return count, round(progress, 1)

def fetch_gwangju_weather():
    """Gemini-search 모델을 이용해 현재 광주광역시의 실시간 날씨를 조회합니다."""
    if not API_URL or not LITELLM_MASTER_KEY:
        return "날씨 정보를 가져올 수 없음 (API 설정 미비)"

    prompt = "오늘 현재 대한민국 광주광역시의 날씨(기온, 하늘 상태, 특이사항)를 아주 짧게 한 문장으로 알려줘."
    
    try:
        headers = {"Authorization": f"Bearer {LITELLM_MASTER_KEY}", "Content-Type": "application/json"}
        payload = {
            "model": SEARCH_MODEL,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.5
        }
        res = requests.post(API_URL, json=payload, headers=headers, timeout=15)
        if res.status_code == 200:
            weather_text = res.json()["choices"][0]["message"]["content"]
            return weather_text.strip()
    except Exception as e:
        print(f"[경고] 날씨 조회 실패: {e}")
    
    return "날씨 정보 조회 실패 (평범한 흐린 날씨)"

def get_aesun_detailed_schedule():
    """애순이의 시간별 상세 스케줄 및 상태를 반환합니다."""
    now = datetime.now()
    hour = now.hour
    weekday = now.weekday()
    is_weekend = (weekday == 6)
    is_sleeping = False

    if 2 <= hour < 6:
        is_sleeping = True
        return "집(침대)", "깊은 취침 중", "자동 사냥 돌려놓고 꿈나라 여행 중", "자는 중", is_sleeping

    if is_weekend:
        if 6 <= hour < 11:
            is_sleeping = True
            return "집(침대)", "꿀같은 일요일 늦잠", "평일의 피로를 잠으로 보충 중", "자는 중", is_sleeping
        elif 11 <= hour < 19:
            return "집(거실)", "배달 음식 먹으며 라그M 접속", "누가 숙제 버스 좀 태워줬으면 좋겠음", "게임 중", False
        else:
            return "집(침대 위)", "내일 출근 공포를 게임으로 잊기", "월요병 도지기 직전의 필사적인 레이드 시청", "게임/휴식 중", False
    else:
        is_saturday = (weekday == 5)
        fatigue_label = " (토요일 특근으로 분노 상승)" if is_saturday else ""

        if 6 <= hour < 8:
            return "출근 버스 안", f"지옥의 출근길{fatigue_label}", "졸면서 단톡방 확인, 저녁 버스 파티 미리 구걸", "이동 중", False
        elif 8 <= hour < 12:
            return "회사(사무실/현장)", "오전 업무 수행 중", "상사 눈 피해 스마트폰 뒤집어놓고 몰래 자사 확인", "일하는 중", False
        elif 12 <= hour < 13:
            return "회사 식당", "점심 빨리 먹고 구석에서 레이드", "밥 먹으면서도 채팅창에서 숙제 파티 탐색", "게임 중", False
        elif 13 <= hour < 19:
            return "회사(생산 현장)", f"오후 업무 진행 중{fatigue_label}", "체력 방전, 그냥 퇴근하고 싶음", "일하는 중", False
        elif 19 <= hour < 21:
            return "퇴근길 버스 안", "기력을 짜낸 길드 채팅", "집 도착 시각 계산하며 버스 예약", "이동 중", False
        else:
            return "집(침대/컴퓨터 앞)", "본격적인 버스 탑승 및 채팅", "고수님들 뒤졸졸 따라다니며 숙제 완료", "게임 중", False

def get_daily_mood():
    moods = [
        "오늘따라 모닝 커피가 정말 맛있어서 기분이 좋다.",
        "유독 피곤해서 만사가 귀찮지만 퇴근 생각만 하며 버티는 중.",
        "동료들과 농담 따먹기를 해서 꽤 신나고 낄낄거리는 중이다.",
        "업무가 너무 많아 울고 싶지만 레이드 아이템 먹을 생각에 참는다.",
        "무미건조하지만 평화로운 하루, 이런 날도 있어야지 싶다."
    ]
    return random.choice(moods)

def get_last_issue():
    if os.path.exists(ISSUE_LOG_FILE):
        try:
            with open(ISSUE_LOG_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            last_time = datetime.fromisoformat(data.get("timestamp", datetime.now().isoformat()))
            if datetime.now() - last_time > timedelta(hours=24):
                return {"title": "평화로운 일상", "description": "지난 사건은 모두 해결되어 특별한 문제 없는 평온한 상태다."}
            return data
        except: return None
    return None

def save_current_issue(issue):
    issue["timestamp"] = datetime.now().isoformat()
    with open(ISSUE_LOG_FILE, "w", encoding="utf-8") as f:
        json.dump(issue, f, ensure_ascii=False)

def generate_dynamic_issue(org_data, weather_info, factory_status):
    location, activity, focus, state, _ = get_aesun_detailed_schedule()
    last_issue = get_last_issue()
    prev_context = f"이전 사건: '{last_issue['title']}' / 상황: {last_issue['description']}" if last_issue else "최근 특별한 사건 없음."
    
    all_members = []
    for dept in org_data["departments"]:
        for member in dept["members"]:
            all_members.append(f"{member.get('prefix', '')} {member['name']} {member['rank']}")
    
    selected = random.sample(all_members, 3)
    
    prompt = (
        f"너는 '포링푸드'의 인간미 넘치는 애순이다.\n"
        f"현재 상황: {location}에서 {activity} 중.\n"
        f"포링푸드 공장 가동 상태: {factory_status}\n"
        f"{prev_context}\n"
        f"등장인물: {', '.join(selected)}\n\n"
        "작성 규칙:\n"
        "1. 이전 사건이 진행 중이라면 해결책을 제시하고, 이미 해결되었다면 그 후일담을 짧게 언급해라.\n"
        "2. 위 등장인물들과 얽힌 새로운 사건을 구성해라.\n"
        "3. **중요: 공장 상태가 좋지 않더라도 비관적으로만 쓰지 마라. 그 안에서 발견한 소소한 재미, 동료와의 엉뚱한 대화, 혹은 긍정적인 반전을 반드시 포함시켜라.**\n"
        "4. 애순이는 6일 근무에 찌들어 있지만, 틈틈이 게임(버스)으로 스트레스를 해소하는 낙천적인 구석이 있다.\n"
        "5. 반드시 JSON 형식으로만 응답: {\"title\": \"...\", \"description\": \"...\"}"
    )

    try:
        headers = {"Authorization": f"Bearer {LITELLM_MASTER_KEY}", "Content-Type": "application/json"}
        payload = {
            "model": LLM_MODEL,
            "messages": [{"role": "system", "content": "너는 사내 사건의 연속성을 기록하는 작가다."}, {"role": "user", "content": prompt}],
            "temperature": 0.8,
            "response_format": {"type": "json_object"}
        }
        res = requests.post(API_URL, json=payload, headers=headers, timeout=15)
        if res.status_code == 200:
            new_issue = json.loads(res.json()["choices"][0]["message"]["content"])
            save_current_issue(new_issue)
            return new_issue
    except Exception as e:
        print(f"[에러] 이슈 생성 실패: {e}")
    
    return {"title": "평범한 하루", "description": "특별한 일 없이 피곤한 하루가 지나가고 있다."}

def get_time_tag():
    now = datetime.now()
    weekday = now.weekday()
    hour = now.hour
    if weekday == 6: return "[일요일/꿀잠/휴식]"
    elif weekday == 5: return "[토요일/지옥특근]"
    if 2 <= hour < 6: return "[심야/취침중]"
    elif 6 <= hour < 9: return "[오전/출근길]"
    elif 19 <= hour < 21: return "[저녁/퇴근길]"
    return "[평일/업무/게임]"