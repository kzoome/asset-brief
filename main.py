import os
import asyncio
import argparse
import re
from datetime import datetime
from dotenv import load_dotenv

# 1. 환경변수 선도 로드 (하위 모듈들이 초기화될 때 환경변수를 사용할 수 있도록)
load_dotenv()

# 환경변수 로드 완료 후 모듈 임포트
from utils.market import get_ticker_name_kr, get_market_data, get_global_market_status
from services.news import get_asset_news, get_market_news
from services.llm import summarize_news, generate_global_insight
from services.notifier import send_telegram_message
from services.dart import get_recent_disclosures

async def main(market: str = "all"):
    print(f"=== 📈 AssetBrief 시작 (market={market}) ===\n")

    # ── 0. 시장 전반 지수 및 뉴스 수집 ──
    market_status = get_global_market_status(market)
    market_news = get_market_news(market)

    # ── 종목 정의 ──
    US_TICKERS = [
        "BRK-B",   # Berkshire Hathaway Class B
        "GOOGL",   # Alphabet Class A
        "MSFT",    # Microsoft
        "TSLA",    # Tesla
        "AAPL",    # Apple
        "AVGO",    # Broadcom
    ]
    KR_TICKERS = [
        "003230.KS",  # 삼양식품
        "009540.KS",  # HD한국조선해양
        "352820.KS",  # 하이브
        "000660.KS",  # SK하이닉스
        "138040.KS",  # 메리츠금융지주
        "298040.KS",  # 효성중공업
        "017670.KS",  # SK텔레콤
    ]

    if market == "us":
        tickers = US_TICKERS
        label = "🇺🇸 미국 주식"
    elif market == "kr":
        tickers = KR_TICKERS
        label = "🇰🇷 한국 주식"
    else:  # all
        tickers = US_TICKERS + KR_TICKERS
        label = "전체"

    all_briefs = []  # 전체 브리핑 누적

    for ticker in tickers:
        try:
            # 0. 종목명 추출
            name = get_ticker_name_kr(ticker)

            # 1. 뉴스 수집 (Retrieval)
            news_data = get_asset_news(ticker, name)
            
            # 2. 시장 데이터 수집 (Market Data)
            market_data = get_market_data(ticker)
            
            # 2.5 DART 공시 데이터 (KR_STOCK)
            if market == "kr" or ticker.endswith(".KS") or ticker.endswith(".KQ"):
                dart_data = get_recent_disclosures(ticker, days=2)
                if dart_data:
                    news_data += "\n\n" + dart_data

            # 3. 뉴스 요약 (Generation)
            briefing = summarize_news(ticker, name, news_data)
            
            # 4. 결과 출력
            result_msg = f"━━━━━━━━━━\n📊 <b>{name} ({ticker})</b>\n{market_data}\n\n{briefing}"
            print(result_msg)
            print("\n" + "="*30 + "\n")

            all_briefs.append(result_msg)

        except Exception as e:
            print(f"❌ [{ticker}] 에러가 발생했습니다: {e}\n")

    # ── 4. 전체 인사이트 도출 ──
    ticker_briefs_summary = ""
    for b in all_briefs:
        # 텔레그램 태그 제거하고 본문만 추출
        clean_b = re.sub(r'<[^>]+>', '', b)
        ticker_briefs_summary += clean_b + "\n"
    
    print(f"📊 분석을 위한 종목 브리핑 요약본 생성 완료 (길이: {len(ticker_briefs_summary)}자)")
    global_insight = generate_global_insight(market_status, market_news, ticker_briefs_summary)

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
    args = parser.parse_args()
    asyncio.run(main(market=args.market))