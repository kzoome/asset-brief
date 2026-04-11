from __future__ import annotations
import os
import asyncio
import argparse
import re
from datetime import datetime
from zoneinfo import ZoneInfo
from dotenv import load_dotenv

# 1. 환경변수 선도 로드 (하위 모듈들이 초기화될 때 환경변수를 사용할 수 있도록)
load_dotenv()

# 환경변수 로드 완료 후 모듈 임포트
from utils.market import get_ticker_name_kr, get_global_market_status
from services.news import get_asset_news
from services.llm import summarize_news_short
from services.notifier import send_telegram_message
from services.dart import get_recent_disclosures
from services.portfolio import load_portfolio, FALLBACK_PORTFOLIO


def is_morning_session(session: str, kst_now: datetime | None = None) -> bool:
    """오전 세션 여부 판단. session='auto'이면 KST 기준 오전(12시 미만)으로 결정."""
    if session == "am":
        return True
    if session == "pm":
        return False
    if kst_now is None:
        kst_now = datetime.now(ZoneInfo("Asia/Seoul"))
    return kst_now.hour < 12


async def main(market: str = "all", session: str = "auto"):
    print(f"=== 📈 AssetBrief 시작 (market={market}, session={session}) ===\n")

    # ── 0. 시장 전반 지수 및 뉴스 수집 ──
    market_status = get_global_market_status(market)

    # ── 포트폴리오 로드 (구글 시트 → 폴백) ──
    portfolio = load_portfolio()

    us_items = [p for p in portfolio if p["market"] == "us"]
    kr_items = [p for p in portfolio if p["market"] == "kr"]

    kst_now = datetime.now(ZoneInfo("Asia/Seoul"))
    morning = is_morning_session(session, kst_now)

    if market == "us":
        items = us_items
        label = "🇺🇸 해외 주식"
    elif market == "kr":
        items = kr_items
        label = "🇰🇷 국내 주식"
    else:  # all
        items = (us_items + kr_items) if morning else (kr_items + us_items)
        label = "전체"

    # ── 1. 점수 계산 및 티어 결정 ──
    def compute_score(item):
        w = item["weight"] if item["weight"] > 0 else 1.0
        return w * abs(item.get("change_1d", 0.0))

    def sort_key(item):
        if morning:
            group = 0 if item["market"] == "us" else 1
        else:
            group = 0 if item["market"] == "kr" else 1
        return (group, -compute_score(item))

    sorted_items = sorted(items, key=sort_key)

    # scan_entries: (name, ticker, weight, change_1d, summary)
    scan_entries = []

    for item in sorted_items:
        ticker = item["ticker"]
        weight = item["weight"]
        change_1d = item.get("change_1d", 0.0)
        name = item["name"] or get_ticker_name_kr(ticker)
        score = compute_score(item)

        try:
            if score > 0:
                news_data = get_asset_news(ticker, name)
                if ticker.endswith((".KS", ".KQ")):
                    dart_data = get_recent_disclosures(ticker, days=2)
                    if dart_data:
                        news_data += "\n\n" + dart_data
                short_summary = await summarize_news_short(ticker, name, news_data)
                scan_entries.append((name, ticker, weight, change_1d, short_summary))
            else:
                scan_entries.append((name, ticker, weight, change_1d, ""))

        except Exception as e:
            print(f"❌ [{ticker}] 에러가 발생했습니다: {e}\n")
            scan_entries.append((name, ticker, weight, change_1d, ""))

    # ── 3. 메시지 파트 조립 ──
    def format_entry(name, ticker, weight, change_1d, summary):
        sign = "+" if change_1d > 0 else ""
        change_str = f"{sign}{change_1d:.1f}%" if change_1d != 0 else "±0.0%"
        weight_str = f"{weight:.1f}%" if weight > 0 else "-"
        arrow = "📈" if change_1d > 0 else ("📉" if change_1d < 0 else "➖")
        line = f"{arrow} <b>{name}</b>  비중 {weight_str} / {change_str}"
        if summary:
            line += f"\n{summary}"
        return line

    # ── 4. 메시지 조립 및 텔레그램 전송 ──
    if not scan_entries:
        print("⚠️ 전송할 브리핑이 없습니다.")
        return

    header = f"📈 AssetBrief 데일리 브리핑 ({label})\n{kst_now.strftime('%Y-%m-%d')}\n\n"
    MAX_LEN = 4096

    all_parts = []
    if market_status:
        all_parts.append(f"<b>[📊 시장 지표]</b>\n{market_status}\n\n")
    all_parts.append("<b>[🔍 오늘의 브리핑]</b>\n\n")
    for entry in scan_entries:
        all_parts.append(format_entry(*entry) + "\n\n")

    all_messages = []
    current = header
    for part in all_parts:
        if len(current) + len(part) > MAX_LEN:
            if current.strip():
                all_messages.append(current.rstrip())
            current = part
        else:
            current += part
    if current.strip():
        all_messages.append(current.rstrip())

    print(f"\n=== 텔레그램 전송 예정 메시지 (총 {len(all_messages)}개 부분) ===")
    for i, msg in enumerate(all_messages, 1):
        print(f"--- Part {i} ---")
        print(re.sub(r'<[^>]+>', '', msg))
    print("=================================\n")

    for i, msg in enumerate(all_messages, 1):
        await send_telegram_message(msg)
        print(f"📤 텔레그램 전송 [{i}/{len(all_messages)}] 완료")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="AssetBrief - 종목 브리핑")
    parser.add_argument(
        "--market",
        choices=["us", "kr", "all"],
        default="all",
        help="실행할 시장 (us=미국, kr=한국, all=전체)"
    )
    parser.add_argument(
        "--session",
        choices=["am", "pm", "auto"],
        default="auto",
        help="브리핑 세션 (am=오전 US→KR, pm=오후 KR→US, auto=시각 자동감지)"
    )
    args = parser.parse_args()
    asyncio.run(main(market=args.market, session=args.session))
