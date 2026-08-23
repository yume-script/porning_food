import json
import requests
from datetime import datetime
from config import API_URL, LITELLM_MASTER_KEY, LLM_MODEL
import processor

# 함수 시그니처에 mood 인자를 추가했습니다.
def generate_aesun_report(issue, time_tag, org_data, persona_data, weather_info, stats, mood):
    """
    processor에서 생성된 '이전 사건 후일담', '오늘의 기분', '생산 통계'를 바탕으로
    애순이의 인간적인 희노애락이 담긴 1인칭 보고서를 생성합니다.
    """
    count, progress = stats # 생산량 통계 언패킹
    main_product = org_data.get("main_product", "포링 젤리")
    
    now = datetime.now()
    current_time_str = f"{now.strftime('%Y-%m-%d')} {now.hour:02d}:00 {time_tag}"
    
    # 상세 상태 가져오기
    location, activity, focus, state, _ = processor.get_aesun_detailed_schedule()
    
    # LLM 시스템 프롬프트: mood 인자를 직접 사용하여 프롬프트 주입
    system_prompt = (
        "너는 가상의 회사 '포링푸드' 생산부 대리이자, 일상 속에서 희노애락을 느끼는 인간적인 '애순이'다.\n"
        "너는 이전 사건이 어떻게 해결되었는지 알고 있으며, 이를 일기처럼 서술한다.\n\n"
        f"--- [현재 상태 및 기분] ---\n"
        f"- 오늘의 기분: {mood}\n"
        f"- 위치: {location}\n"
        f"- 현재 활동: {activity}\n"
        f"- 현재 심리: {focus}\n"
        f"- 현재 날씨: {weather_info}\n"
        f"- 우리 회사 주력 제품: {main_product}\n"
        f"- 현재 생산 현황: {main_product} {count}건 달성 (목표 대비 {progress}%)\n\n"
        "--- [애순이의 캐릭터 특징] ---\n"
        "1. 주 6일 근무하는 생산부 대리. 업무 스트레스와 일상의 소소한 행복(커피, 농담 등)을 동시에 느낀다.\n"
        "2. 게임 '라그나로크M' 중독자이자 버스 승객. 채팅창에서만 열정적이고 현생에서는 피곤하다.\n"
        "3. 업무 상황과 게임 상황을 섞어서 시니컬하지만 유머러스하게 표현한다.\n"
        "4. **매우 중요**: 오늘 기분이 안 좋더라도 무조건 부정적으로만 쓰지 마라. 기분이 {mood}이므로, 이를 애순이 특유의 방식으로 유머러스하게 승화하거나, '그래도 퇴근 후엔 보상받을 거야'라는 긍정적인 반전을 반드시 포함해라.\n\n"
        "작성 지침:\n"
        "- 제공된 [오늘의 사건]을 바탕으로 애순이의 독백을 작성해라.\n"
        "- 이전 사건에 대한 후일담을 1~2문장에 반드시 포함하며, 그때 느꼈던 감정을 섞어라.\n"
        "- '오늘의 기분'과 '생산 현황'을 반영하여 보고서를 작성해라.\n"
        "- 반드시 아래 키를 가진 JSON 객체로 응답: {\"narrative\": \"...\", \"game_status\": \"...\", \"cynical_thought\": \"...\"}"
    )

    user_prompt = f"[오늘의 사건]\n제목: {issue['title']}\n내용: {issue['description']}"

    if API_URL and LITELLM_MASTER_KEY:
        try:
            headers = {
                "Authorization": f"Bearer {LITELLM_MASTER_KEY}",
                "Content-Type": "application/json"
            }
            payload = {
                "model": LLM_MODEL,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                "temperature": 0.8,
                "response_format": {"type": "json_object"}
            }
            
            res = requests.post(API_URL, json=payload, headers=headers, timeout=15)
            if res.status_code == 200:
                result = res.json()
                content_str = result["choices"][0]["message"]["content"]
                parsed_data = json.loads(content_str)
                
                # 페르소나 템플릿에 데이터 주입
                formatted_report = persona_data["speech_style"]["formatting_template"].format(
                    current_time=current_time_str,
                    title=issue['title'],
                    narrative=parsed_data.get("narrative", ""),
                    ragnarok_status=parsed_data.get("game_status", ""),
                    cynical_thought=parsed_data.get("cynical_thought", "")
                )
                
                parsed_data["full_report"] = formatted_report
                return parsed_data
                
        except Exception as e:
            print(f"[경고] LLM 보고서 생성 중 오류 발생: {e}")

    # Fallback 로직도 동일하게 mood를 반영
    fallback_narrative = (
        f"어제 {issue.get('title', '일')}은 해결된 것 같은데, 오늘도 {location}에서 {activity}라니... "
        f"기분은 '{mood}'지만, {main_product} 생산률 {progress}%인 상태로 오늘도 힘내서 채팅창에 '버스 부탁드려요!'라고 올리고 버텨봅니다."
    )
    fallback_game_status = "버스 탑승 대기 중, 채팅창 밑밥 깔기 시전"
    fallback_cynical = "희노애락 다 겪어도 결국 생산량 채우고 퇴근 후엔 라그나로크뿐이다."
    
    formatted_report = persona_data["speech_style"]["formatting_template"].format(
        current_time=current_time_str,
        title=issue.get('title', '오늘의 사건'),
        narrative=fallback_narrative,
        ragnarok_status=fallback_game_status,
        cynical_thought=fallback_cynical
    )
    
    return {
        "narrative": fallback_narrative,
        "game_status": fallback_game_status,
        "cynical_thought": fallback_cynical,
        "full_report": formatted_report
    }