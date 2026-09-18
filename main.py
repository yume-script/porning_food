import os
import json
import random
from datetime import datetime

import loader
import processor
import generator
import notifier
import checker
import characters
from config import INTERACTION_HOURS


def _run_world_tick(aesun_status: dict) -> None:
    """
    [신규] 애순이 파이프라인이 끝난 뒤 호출한다 - 애순이를 제외한 전원의 상태를 갱신하고,
    지정된 시각(INTERACTION_HOURS, 기본 하루 3번)에만 같은 장소에 있는 두 인물을 찾아
    LLM으로 짧은 상호작용 이벤트를 만든다(그 외 시간엔 LLM 호출 없이 상태만 갱신).
    """
    now = datetime.now()
    rnd = random.Random(now.strftime("%Y-%m-%d-%H"))  # 시간대별 고정, 애순이 스케줄 시드와 동일 방식

    roster = characters.load_roster()
    if not roster:
        print("[경고] 조직도를 못 읽어서 다인물 틱을 건너뜁니다.")
        return
    roster_map = characters.roster_by_id(roster)

    aesun_state = {
        "location": aesun_status.get("location"),
        "activity": aesun_status.get("activity"),
        "state": aesun_status.get("state"),
        "updated_at": now.isoformat(),
    }
    states = characters.update_all_states(roster, rnd, aesun_state=aesun_state)
    print(f"[다인물] {len(states)}명 상태 갱신 완료")

    # 애순이가 아닌 인물들의 상태도 히스토리에 한 줄씩 남긴다 (LLM 없이, 가벼움)
    for cid, info in states.items():
        name = info.get("name", cid)
        if name == "애순이":
            continue
        characters.append_character_history(name, {
            "timestamp": now.isoformat(),
            "time_tag": processor.get_time_tag(),
            "location": info.get("location"),
            "activity": info.get("activity"),
            "state": info.get("state"),
        })

    if now.hour not in INTERACTION_HOURS:
        return

    pair = characters.find_colocated_pair(states, rnd)
    if not pair:
        print("[다인물] 이번 시각엔 같은 장소에 있는 인물 쌍이 없어 상호작용을 건너뜁니다.")
        return

    print(f"[다인물] 상호작용 시도: {pair[0]} x {pair[1]}")
    result = characters.generate_interaction(pair, states, roster_map)
    if not result:
        print("[다인물] 상호작용 생성 실패 (LLM 미설정이거나 오류)")
        return

    episode_text = (
        f"👥 [{result['location']}에서 우연히] {result['participants'][0]} x {result['participants'][1]}\n"
        f"{result['episode']}"
    )
    for name in result["participants"]:
        characters.append_character_history(name, {
            "timestamp": now.isoformat(),
            "time_tag": processor.get_time_tag(),
            "location": result["location"],
            "activity": f"{result['participants'][1] if name == result['participants'][0] else result['participants'][0]}와 상호작용",
            "state": "상호작용 중",
            "narrative": result["episode"],
        })

    notifier.send_to_discord(episode_text)
    notifier.send_to_local_bot(episode_text)
    print(f"[다인물] 상호작용 전송 완료: {episode_text}")


def main():
    """
    애순이 봇 메인 파이프라인
    1. 스케줄 확인 및 생산량 통계/서버 상태 점검
    2. 자는 중이면 상태 업데이트 후 종료
    3. 깨어있으면 날씨/공장상태/이슈 생성/보고서 작성/전송
    4. [신규] 애순이 외 인물들의 세계도 같이 굴린다 (다인물 시뮬레이션)
    """
    # 1. 현재 스케줄 및 상태 확인
    location, activity, focus, state, is_sleeping = processor.get_aesun_detailed_schedule()
    time_tag = processor.get_time_tag()
    now_str = datetime.now().isoformat()

    # [통계] 생산량 및 오늘의 기분 가져오기
    prod_count, progress_rate = processor.get_production_stats()
    stats = (prod_count, progress_rate)
    mood = processor.get_daily_mood()  # [추가] 애순이의 감정 상태 반영

    print(f"[통계] 현재 생산량: {prod_count}건 ({progress_rate}%)")
    print(f"[감정] 오늘의 애순이: {mood}")

    # 2. 취침 중일 경우 처리
    if is_sleeping:
        print(f"[정보] 현재 애순이는 자는 시간입니다 ({state}). 상태 파일만 업데이트합니다.")
        status_payload = {
            "timestamp": now_str,
            "time_tag": time_tag,
            "title": "애순이는 취침 중",
            "location": location,
            "activity": activity,
            "narrative": f"지금은 애순이가 {location}에서 {activity} 시간입니다. 건드리지 마세요.",
            "ragnarok_status": "캐릭터는 마을에서 자동 낚시 중이거나 휴식 중",
            "cynical_thought": "잠은 죽어서 자는 거라지만, 내일 출근하려면 지금 자야 한다.",
            "full_report": f"[{time_tag}] 애순이는 현재 자는 중입니다... Zzz",
            "state": state
        }
        notifier.save_to_file(status_payload)
        notifier.append_to_history(status_payload)
        _run_world_tick(status_payload)
        return

    # 3. 깨어있는 시간일 경우: 전체 파이프라인 실행
    print(f"[정보] 애순이 활동 시작: {state} 모드")

    # 포링푸드 공장 상태 확인
    factory_msg, is_factory_ok = checker.check_poring_factory_status()
    print(f"[체크] 포링푸드 공장 상태: {factory_msg}")

    # 리소스 로드
    org_data, _, persona_data = loader.load_resources()

    # 실시간 날씨 정보 가져오기
    print("[1/4] 광주 실시간 날씨 조회 중...")
    weather_info = processor.fetch_gwangju_weather()

    # 실시간 이슈 생성
    print("[2/4] 조직도 기반 동적 이슈 생성 중...")
    dynamic_issue = processor.generate_dynamic_issue(org_data, weather_info, factory_status=factory_msg, our_count=prod_count)

    # 애순이 페르소나 주입 및 보고서 변환 (생산 통계 + 기분 반영)
    print("[3/4] 애순이 시점으로 보고서 변환 중...")
    report_data = generator.generate_aesun_report(
        dynamic_issue, time_tag, org_data, persona_data, weather_info, stats, mood
    )

    # 4. 결과 저장 및 전송
    if report_data:
        print("[4/4] 결과 데이터 저장 및 전송 중...")
        status_payload = {
            "timestamp": now_str,
            "time_tag": time_tag,
            "title": dynamic_issue.get('title', '오늘의 사건'),
            "location": location,
            "activity": activity,
            "weather": weather_info,
            "factory_status": factory_msg,
            "state": state,
            "mood": mood,  # 상태 로그에 기분 추가
            **report_data
        }

        # 로컬 파일 저장
        notifier.save_to_file(status_payload)
        notifier.append_to_history(status_payload)
        _run_world_tick(status_payload)

        # 카카오톡 전송용 메시지 가공
        full_text = report_data["full_report"]
        target_phrase = "💬 애순이의 한마디"
        if target_phrase in full_text:
            katalk_msg = full_text.replace(target_phrase, f"\n━━━━━━━━━━━━━━\n{'\u200b' * 500}\n{target_phrase}")
        else:
            katalk_msg = full_text

        # 외부 채널 전송
        notifier.send_to_discord(full_text)
        notifier.send_to_local_bot(katalk_msg)

        print(f"\n=== [전송 완료] ===\n{full_text}\n")
    else:
        print("[오류] 보고서 생성에 실패하여 전송을 취소합니다.")


if __name__ == "__main__":
    main()
