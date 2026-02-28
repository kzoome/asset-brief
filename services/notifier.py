import os
import re
from telegram import Bot

def _auto_link_urls(text: str) -> str:
    """HTML <a> 태그로 감싸지지 않은 bare URL을 자동으로 클릭 가능한 링크로 변환합니다."""
    # 이미 <a href="..."> 안에 있는 URL은 건드리지 않고, bare URL만 변환
    # URL 끝의 괄호/마침표 등은 제외
    return re.sub(
        r'(?<!href=["\'])(?<!>)(https?://[^\s\)<>]+)',
        r'<a href="\1">링크</a>',
        text
    )

async def send_telegram_message(message: str):
    """텔레그램 봇을 통해 메시지를 전송합니다."""
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")

    if token and chat_id:
        try:
            bot = Bot(token=token)
            linked_message = _auto_link_urls(message)
            await bot.send_message(chat_id=chat_id, text=linked_message, parse_mode="HTML")
        except Exception as e:
            print(f"⚠️ 텔레그램 메시지 전송 실패: {e}")
    else:
        print("⚠️ 텔레그램 설정(TOKEN, CHAT_ID)이 없어 메시지를 보내지 않습니다.")
