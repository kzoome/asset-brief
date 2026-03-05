import os
import asyncio
import argparse
import re
from datetime import datetime
from dotenv import load_dotenv

# 1. 환경변수 선도 로드 (하위 모듈들이 초기화될 때 환경변수를 사용할 수 있도록)
load_dotenv()

# 환경변수 로드 완료 후 모듈 임포트
from utils.market import get_ticker_name_kr, get_market_data, get_global_market_status, get_upcoming_events, is_etf
from services.news import get_asset_news, get_market_news
from services.llm import summarize_news, generate_global_insight, extract_core_trend, extract_etf_queries
from services.notifier import send_telegram_message
from services.dart import get_recent_disclosures
from services.portfolio import load_portfolio, FALLBACK_PORTFOLIO

def is_morning_session(session: str) -> bool:
    """오전 세션 여부 판단. session='auto'이면 현재 시각 기준 오전(12시 미만)으로 결정."""
    if session == "am":
        return True
    if session == "pm":
        return False
    # auto: 현재 로컬 시각 기준
    return datetime.now().hour < 12


async def main(market: str = "all", session: str = "auto"):
    print(f"=== 📈 AssetBrief 시작 (market={market}, session={session}) ===\n")

    # ── 0. 시장 전반 지수 및 뉴스 수집 ──
    market_status = get_global_market_status(market)
    market_news = get_market_news(market)

    # ── 포트폴리오 로드 (구글 시트 → 폴백) ──
    portfolio = load_portfolio()

    us_items = [p for p in portfolio if p["market"] == "us"]
    kr_items = [p for p in portfolio if p["market"] == "kr"]

    morning = is_morning_session(session)

    if market == "us":
        items = us_items
        label = "🇺🇸 해외 주식"
    elif market == "kr":
        items = kr_items
        label = "🇰🇷 국내 주식"
    else:  # all
        items = (us_items + kr_items) if morning else (kr_items + us_items)
        label = "전체"

    scored_briefs = []  # (score, result_msg) 리스트

    for item in items:
        ticker = item["ticker"]
        weight = item["weight"]
        try:
            # 0. 종목명 추출 (포트폴리오 name 우선, 없으면 기존 매핑 사용)
            name = item["name"] or get_ticker_name_kr(ticker)

            # 1. 뉴스 수집 (Retrieval)
            etf_q = None
            if is_etf(ticker, name):
                is_kr = ticker.endswith(".KS") or ticker.endswith(".KQ")
                etf_q = await extract_etf_queries(ticker, name, is_kr)
            news_data = get_asset_news(ticker, name, etf_queries=etf_q)

            # 2. 시장 데이터 수집 (Market Data)
            market_data = get_market_data(ticker)
            change_1d = item.get("change_1d", 0.0)  # 구글 시트에서 가져온 1d 변동률

            # 2.5 DART 공시 데이터 (KR_STOCK, ETF 제외)
            if not etf_q and (ticker.endswith(".KS") or ticker.endswith(".KQ")):
                dart_data = get_recent_disclosures(ticker, days=2)
                if dart_data:
                    news_data += "\n\n" + dart_data

            # 3. 뉴스 요약 (Generation)
            briefing = await summarize_news(ticker, name, news_data)

            # 3-1. 핵심 트렌드 1문장 초고속 추출
            core_trend = await extract_core_trend(ticker, briefing)

            # 3-2. 실적발표/배당 캘린더 경고
            events = get_upcoming_events(ticker)

            # 4. 메시지 조립
            trend_prefix = f"<b>{core_trend}</b>\n\n" if core_trend else ""
            events_line = f"\n{events}" if events else ""
            impact_bp = weight * change_1d  # (%) × (%) = bp
            meta_parts = []
            if weight > 0:
                meta_parts.append(f"비중 {weight:.1f}%")
            if weight > 0 and change_1d != 0:
                meta_parts.append(f"임팩트 {impact_bp:+.1f}bp")
            meta_line = f"\n{' · '.join(meta_parts)}" if meta_parts else ""
            result_msg = f"━━━━━━━━━━\n<b>{name} ({ticker})</b>{meta_line}\n{market_data}{events_line}\n\n{trend_prefix}{briefing}"

            # 정렬 점수: 비중 × |1D 변동률| (비중 없을 경우 변동률만 사용)
            score = (weight if weight > 0 else 1.0) * abs(change_1d)
            scored_briefs.append((score, result_msg, item["market"]))

        except Exception as e:
            print(f"❌ [{ticker}] 에러가 발생했습니다: {e}\n")

    # 오전: 해외 먼저 / 국내 나중에, 오후: 국내 먼저 / 해외 나중에, 각 그룹 내 비중×|1d| 내림차순
    def sort_key(x):
        score, _, item_market = x
        if morning:
            group = 0 if item_market == "us" else 1
        else:
            group = 0 if item_market == "kr" else 1
        return (group, -score)

    scored_briefs.sort(key=sort_key)
    all_briefs = [msg for _, msg, _ in scored_briefs]

    for msg in all_briefs:
        print(msg)
        print("\n" + "=" * 30 + "\n")

    # ── 4. 전체 인사이트 도출 ──
    try:
        # 글로벌 인사이트 생성이 너무 오래 걸릴 경우(45초) 타임아웃 처리
        global_insight = await asyncio.wait_for(generate_global_insight(market_status, market_news), timeout=45.0)
    except asyncio.TimeoutError:
        print("⚠️ Global Insight 생성 타임아웃 (45초 초과). Flash 모델로 폴백합니다.")
        # generate_global_insight 내부에서도 예외 발생 시 Flash로 재시도하지만, 
        # 비동기 대기 자체를 중단시키기 위해 여기서도 fallback 호출 가능. 
        # 여기서는 단순히 타임아웃 알림 후 빈값 처리하거나 내부 fallback을 신뢰함.
        # 사실 generate_global_insight 내부에서 Flash 재시도를 하므로, 위 wait_for는 전체 안전장치임.
        global_insight = "⚠️ 시장 인사이트 생성 시간이 초과되었습니다. (서버 응답 지연)"
    except Exception as e:
        print(f"⚠️ Global Insight 도출 중 비기대 에러: {e}")
        global_insight = ""

    # 5. 전체 브리핑을 하나로 합쳐서 텔레그램 전송
    if all_briefs:
        header = f"📈 AssetBrief 데일리 브리핑 ({label})\n{datetime.now().strftime('%Y-%m-%d')}\n\n"
        
        # 인사이트 섹션 추가
        content_parts = []
        if global_insight:
            content_parts.append(global_insight + "\n\n" + "━" * 15 + "\n")
        
        if market_status:
            content_parts.append(f"<b>[📊 시장 지표]</b>\n{market_status}\n\n")
            
        content_parts.extend(all_briefs)
        
        full_message = header + "\n\n".join(content_parts)

        # 텔레그램 메시지 최대 길이(4096자) 초과 시 자동 분할 전송
        MAX_LEN = 4096
        
        if len(full_message) <= MAX_LEN:
            print("\n=== 텔레그램 전송 예정 메시지 ===")
            print(re.sub(r'<[^>]+>', '', full_message))
            print("=================================\n")
            await send_telegram_message(full_message)
            print("📤 텔레그램 전송 완료")
        else:
            chunks = []
            current = header
            
            # 모든 구성요소를 하나의 리스트로 통합하여 순차적으로 청크 체킹
            all_parts = []
            if global_insight:
                all_parts.append(global_insight + "\n\n" + "━" * 15 + "\n")
            if market_status:
                all_parts.append(f"<b>[📊 시장 지표]</b>\n{market_status}\n\n")
            for brief in all_briefs:
                all_parts.append(brief + "\n\n")
                
            for part in all_parts:
                if len(current) + len(part) > MAX_LEN:
                    # 현재 쌓인 current가 있다면 먼저 청크로 분리
                    if current.strip():
                        chunks.append(current.rstrip())
                    # 그리고 새로운 current는 새 파트로 시작
                    current = part
                else:
                    current += part
                    
            if current.strip():
                chunks.append(current.rstrip())
            print(f"\n=== 텔레그램 전송 예정 메시지 (총 {len(chunks)}개 부분) ===")
            for i, chunk in enumerate(chunks, 1):
                print(f"--- Part {i} ---")
                print(re.sub(r'<[^>]+>', '', chunk))
            print("=================================\n")
            
            for i, chunk in enumerate(chunks, 1):
                await send_telegram_message(chunk)
                print(f"📤 텔레그램 전송 [{i}/{len(chunks)}] 완료")

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