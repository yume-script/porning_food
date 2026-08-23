import os
import json
import requests
from datetime import datetime
from config import DISCORD_WEBHOOK_URL, LOCAL_BOT_URL, ROOM_ID, STATUS_OUT_PATH

def save_to_file(status_data):
    try:
        os.makedirs(os.path.dirname(STATUS_OUT_PATH), exist_ok=True)
        with open(STATUS_OUT_PATH, "w", encoding="utf-8") as f:
            json.dump(status_data, f, ensure_ascii=False, indent=2)
        print(f"[성공] 상태 저장 완료: {STATUS_OUT_PATH}")
    except Exception as e:
        print(f"[에러] 파일 저장 실패: {e}")

def send_to_discord(text):
    if not DISCORD_WEBHOOK_URL or "YOUR_ACTUAL_TOKEN" in DISCORD_WEBHOOK_URL:
        return
    try:
        requests.post(DISCORD_WEBHOOK_URL, json={"content": text}, timeout=5)
        print("[성공] Discord 전송 완료")
    except Exception as e:
        print(f"[에러] Discord 전송 실패: {e}")

def send_to_local_bot(text):
    if not LOCAL_BOT_URL:
        return
    payload = {"type": "text", "room": ROOM_ID, "data": text}
    try:
        requests.post(LOCAL_BOT_URL, json=payload, timeout=5)
        print(f"[성공] 로컬 봇 전송 완료 (Room: {ROOM_ID})")
    except Exception as e:
        print(f"[에러] 로컬 봇 전송 실패: {e}")

