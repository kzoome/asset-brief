import os
import asyncio
from dotenv import load_dotenv

# 1. 환경변수 선도 로드 (하위 모듈들이 초기화될 때 환경변수를 사용할 수 있도록)
load_dotenv()

# 환경변수 로드 완료 후 모듈 임포트
from utils.market import get_ticker_name, get_market_data
from services.news import get_asset_news
from services.llm import summarize_news
from services.notifier import send_telegram_message

async def main():
    print("=== 📈 AssetBrief MVP 시작 ===\n")
    
    # 여러 자산(미국 주식, 국내 주식 등)을 리스트로 관리
    tickers = ["MSFT", "TSLA", "AAPL"]
    for ticker in tickers:
        try:
            # 0. 종목명 추출
            name = get_ticker_name(ticker)

            # 1. 뉴스 수집 (Retrieval)
            news_data = get_asset_news(ticker, name)
            
            # 2. 시장 데이터 수집 (Market Data)
            market_data = get_market_data(ticker)

            # 3. 뉴스 요약 (Generation)
            briefing = summarize_news(ticker, news_data)
            
            # 4. 결과 출력
            result_msg = f"📊 [오늘의 {ticker} ({name}) 브리핑]\n{market_data}\n\n{briefing}"
            print(result_msg)
            print("\n" + "="*30 + "\n")

            # 5. 텔레그램 전송
            await send_telegram_message(result_msg)
            
        except Exception as e:
            print(f"❌ [{ticker}] 에러가 발생했습니다: {e}\n")

if __name__ == "__main__":
    asyncio.run(main())