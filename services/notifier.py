import os
import re
from urllib.parse import urlparse
from telegram import Bot

def _domain_label(url: str) -> str:
    """URL에서 출처 도메인명을 추출합니다. (예: hankyung.com → hankyung)"""
    try:
        host = urlparse(url).netloc.lower()  # e.g. 'www.hankyung.com'
        host = re.sub(r'^www\.', '', host)   # www 제거
        # SLD 추출: co.kr, com, net 등 앞의 이름만 사용
        parts = host.split('.')
        if len(parts) >= 3 and parts[-2] in ('co', 'com', 'or', 'ne', 'go'):
            # e.g. news.naver.co.kr → naver
            return parts[-3]
        # e.g. hankyung.com → hankyung, finance.yahoo.com → yahoo
        return parts[-2] if len(parts) >= 2 else parts[0]
    except Exception:
        return '링크'

def _auto_link_urls(text: str) -> str:
    """HTML <a> 태그로 감싸지지 않은 bare URL을 자동으로 클릭 가능한 링크로 변환합니다.
    연속된 링크 전용 줄은 공백으로 이어 한 줄로 표시합니다."""
    def _replace_url(match):
        url = match.group(1)
        safe_url = url.replace("&", "&amp;")
        label = _domain_label(url)
        return f'<a href="{safe_url}">{label}</a>'

    text = re.sub(
        r'(?<!href=["\'])(?<!>)(https?://[^\s\)<>]+)',
        _replace_url,
        text
    )

    # 링크만 있는 줄이 연속될 경우 한 줄로 합치기
    link_line = re.compile(r'^\s*<a href="[^"]+">[^<]+</a>\s*$')
    lines = text.split('\n')
    result = []
    link_group = []
    for line in lines:
        if link_line.match(line):
            link_group.append(line.strip())
        else:
            if link_group:
                result.append(' '.join(link_group))
                link_group = []
            result.append(line)
    if link_group:
        result.append(' '.join(link_group))

    return '\n'.join(result)

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
