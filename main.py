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
from utils.market import get_ticker_name_kr, get_market_data, get_global_market_status, get_upcoming_events, is_etf
from services.news import get_asset_news
from services.llm import summarize_news, summarize_news_short, extract_core_trend, extract_etf_queries
from services.notifier import send_telegram_message
from services.dart import get_recent_disclosures
from services.portfolio import load_portfolio, FALLBACK_PORTFOLIO

# 상세 브리핑을 생성할 상위 종목 수 (비중×|변동률| 기준)
HIGH_N = 3


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

    # 시장별 상위 HIGH_N 종목 → HIGH 티어
    high_tickers = set()
    for mkt in ("us", "kr"):
        mkt_items = [i for i in sorted_items if i["market"] == mkt]
        top_n = min(HIGH_N, len(mkt_items))
        for item in sorted(mkt_items, key=compute_score, reverse=True)[:top_n]:
            high_tickers.add(item["ticker"])

    # scan_entries: (name, ticker, change_1d, one_liner, is_high)
    scan_entries = []
    detail_briefs = []  # HIGH 종목 상세 브리핑 메시지 (시장 순서 유지)

    for item in sorted_items:
        ticker = item["ticker"]
        weight = item["weight"]
        change_1d = item.get("change_1d", 0.0)
        name = item["name"] or get_ticker_name_kr(ticker)
        is_high = ticker in high_tickers
        score = compute_score(item)

        try:
            market_data = get_market_data(ticker)
            events = get_upcoming_events(ticker)

            if is_high:
                # ── HIGH 티어: 전체 파이프라인 ──
                etf_q = None
                if is_etf(ticker, name):
                    is_kr_etf = ticker.endswith((".KS", ".KQ"))
                    etf_q = await extract_etf_queries(ticker, name, is_kr_etf)
                news_data = get_asset_news(ticker, name, etf_queries=etf_q)
                if not etf_q and ticker.endswith((".KS", ".KQ")):
                    dart_data = get_recent_disclosures(ticker, days=2)
                    if dart_data:
                        news_data += "\n\n" + dart_data
                briefing = await summarize_news(ticker, name, news_data)
                core_trend = await extract_core_trend(ticker, briefing)

                # 상세 브리핑 메시지 조립
                trend_prefix = f"<b>{core_trend}</b>\n\n" if core_trend else ""
                events_line = f"\n{events}" if events else ""
                meta_parts = []
                if weight > 0:
                    meta_parts.append(f"비중 {weight:.1f}%")
                if weight > 0 and change_1d != 0:
                    meta_parts.append(f"임팩트 {weight * change_1d:+.1f}bp")
                meta_line = f"\n{' · '.join(meta_parts)}" if meta_parts else ""
                detail_msg = f"━━━━━━━━━━\n<b>{name} ({ticker})</b>{meta_line}\n{market_data}{events_line}\n\n{trend_prefix}{briefing}"
                detail_briefs.append(detail_msg)
                scan_entries.append((name, ticker, change_1d, core_trend, True))
                print(detail_msg)
                print()

            elif score > 0:
                # ── MID 티어: 단문 요약만 ──
                news_data = get_asset_news(ticker, name)
                if ticker.endswith((".KS", ".KQ")):
                    dart_data = get_recent_disclosures(ticker, days=2)
                    if dart_data:
                        news_data += "\n\n" + dart_data
                short_summary = await summarize_news_short(ticker, name, news_data)
                scan_entries.append((name, ticker, change_1d, short_summary, False))

            else:
                # ── LOW 티어: API 호출 없음 ──
                scan_entries.append((name, ticker, change_1d, "", False))

        except Exception as e:
            print(f"❌ [{ticker}] 에러가 발생했습니다: {e}\n")
            scan_entries.append((name, ticker, change_1d, "", is_high))

    global_insight = ""

    # ── 3. 스캔 뷰 조립 ──
    def format_scan_line(name, ticker, change_1d, summary, is_high):
        sign = "+" if change_1d > 0 else ""
        change_str = f"{sign}{change_1d:.1f}%" if change_1d != 0 else "±0.0%"
        star = " ★" if is_high else ""
        line = f"<b>{name}</b>  {change_str}{star}"
        if summary:
            line += f"\n{summary}"
        return line

    scan_lines = [format_scan_line(*e) for e in scan_entries]
    scan_section = "<b>[🔍 오늘의 요약]</b>\n" + "\n\n".join(scan_lines)
    if any(e[4] for e in scan_entries):
        scan_section += "\n\n★ 상세 브리핑은 아래 메시지 참조"

    # ── 4. 메시지 조립 및 텔레그램 전송 ──
    if not scan_entries:
        print("⚠️ 전송할 브리핑이 없습니다.")
        return

    header = f"📈 AssetBrief 데일리 브리핑 ({label})\n{kst_now.strftime('%Y-%m-%d')}\n\n"
    MAX_LEN = 4096

    # 첫 번째 메시지: 인사이트 + 시장 지표 + 스캔 뷰
    first_parts = []
    if global_insight:
        first_parts.append(global_insight + "\n\n" + "━" * 15 + "\n\n")
    if market_status:
        first_parts.append(f"<b>[📊 시장 지표]</b>\n{market_status}\n\n")
    first_parts.append(scan_section)

    all_messages = []

    # 첫 메시지 분할 (4096자 초과 시)
    current = header
    for part in first_parts:
        if len(current) + len(part) > MAX_LEN:
            if current.strip():
                all_messages.append(current.rstrip())
            current = part
        else:
            current += part
    if current.strip():
        all_messages.append(current.rstrip())

    # 이후 메시지: HIGH 종목 상세 브리핑
    if detail_briefs:
        current = ""
        for brief in detail_briefs:
            chunk = brief + "\n\n"
            if len(current) + len(chunk) > MAX_LEN:
                if current.strip():
                    all_messages.append(current.rstrip())
                current = chunk
            else:
                current += chunk
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
