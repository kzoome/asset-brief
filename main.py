import os
import asyncio
import argparse
from datetime import datetime
from dotenv import load_dotenv

# 1. 환경변수 선도 로드 (하위 모듈들이 초기화될 때 환경변수를 사용할 수 있도록)
load_dotenv()

# 환경변수 로드 완료 후 모듈 임포트
from utils.market import get_ticker_name_kr, get_market_data
from services.news import get_asset_news
from services.llm import summarize_news
from services.notifier import send_telegram_message

async def main(market: str = "all"):
    print(f"=== 📈 AssetBrief 시작 (market={market}) ===\n")

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

            # 3. 뉴스 요약 (Generation)
            briefing = summarize_news(ticker, name, news_data)
            
            # 4. 결과 출력
            result_msg = f"━━━━━━━━━━\n📊 <b>{name} ({ticker})</b>\n{market_data}\n\n{briefing}"
            print(result_msg)
            print("\n" + "="*30 + "\n")

            all_briefs.append(result_msg)

        except Exception as e:
            print(f"❌ [{ticker}] 에러가 발생했습니다: {e}\n")

    # 5. 전체 브리핑을 하나로 합쳐서 텔레그램 전송
    if all_briefs:
        header = f"📈 AssetBrief 데일리 브리핑 ({label})\n{datetime.now().strftime('%Y-%m-%d')}\n\n"
        full_message = header + "\n\n".join(all_briefs)

        # 텔레그램 메시지 최대 길이(4096자) 초과 시 자동 분할 전송
        MAX_LEN = 4096
        import re
        
        if len(full_message) <= MAX_LEN:
            print("\n=== 텔레그램 전송 예정 메시지 ===")
            print(re.sub(r'<[^>]+>', '', full_message))
            print("=================================\n")
            await send_telegram_message(full_message)
            print("📤 텔레그램 전송 완료")
        else:
            chunks = []
            current = header
            for brief in all_briefs:
                segment = brief + "\n\n"
                if len(current) + len(segment) > MAX_LEN:
                    chunks.append(current.rstrip())
                    current = segment
                else:
                    current += segment
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