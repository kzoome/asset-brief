import os
from telegram import Bot

async def send_telegram_message(message: str):
    """텔레그램 봇을 통해 메시지를 전송합니다."""
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")

    if token and chat_id:
        try:
            bot = Bot(token=token)
            await bot.send_message(chat_id=chat_id, text=message)
        except Exception as e:
            print(f"⚠️ 텔레그램 메시지 전송 실패: {e}")
    else:
        print("⚠️ 텔레그램 설정(TOKEN, CHAT_ID)이 없어 메시지를 보내지 않습니다.")
