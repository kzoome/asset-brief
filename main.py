import os
import asyncio
from dotenv import load_dotenv
from tavily import TavilyClient
from google import genai
from google.genai import types
from telegram import Bot
import yfinance as yf

# 1. 환경변수 로드
load_dotenv()

# 2. 클라이언트 초기화
tavily_client = TavilyClient(api_key=os.getenv("TAVILY_API_KEY")) if os.getenv("TAVILY_API_KEY") else None
gemini_client = genai.Client(api_key=os.getenv("GOOGLE_API_KEY")) if os.getenv("GOOGLE_API_KEY") else None

# 3. 자산군별 프롬프트 정의
SYSTEM_PROMPTS = {
    "US_STOCK": """
    너는 월가에서 가장 신뢰받는 주식 애널리스트야.
    제공된 뉴스를 바탕으로 주가 변동의 원인을 '월가 투자의견' 관점에서 분석해줘.
    분석 시에는 뉴스들이 실적/펀더멘털에 미칠 수 있는 영향을 중점적으로 바라봐줘.
    차트 혹은 주가의 흐름에 대한 기술적 분석보다는 뉴스 뒤에 숨겨진 의미와 실질적으로 실적/펀더멘탈에 미치는 영향에 대해 집중할 것.
    
    [출력 규칙]
    1. 글머리 기호(-)를 사용하여 3줄로 요약할 것.
    2. 기업의 실적 발표나 IB 리포트가 있다면 우선적으로 언급할 것.
    3. 단순한 시세 중계보다는 '왜' 움직였는지에 집중할 것.
    """,
    "KR_STOCK": """
    너는 한국 주식 시장에 정통한 여의도 주식 애널리스트야.
    제공된 뉴스는 [Global/English]와 [Local/Korean] 섹션으로 구분되어 있다.
    이 두 가지 시각을 분리하여 각각 3줄씩 요약해줘.
    
    [출력 규칙]
    1. **[🌏 외신]** 섹션:
       - 외신 뉴스(Global/English)를 바탕으로 외국인 투자자 시각, 글로벌 매크로/공급망 이슈, 해외 IB 의견을 분석하여 3줄 요약.
    2. **[🇰🇷 국내]** 섹션:
       - 국내 뉴스(Local/Korean)를 바탕으로 국내 수급, 공시(Dart), 여의도 증권가 리포트/찌라시 내용을 분석하여 3줄 요약.
    
    각 줄은 글머리 기호(-)로 시작하고, 단순 시세 나열이 아닌 '주가 변동의 원인'과 '펀더멘털 영향'에 집중할 것.
    """
}

def get_asset_type(ticker: str) -> str:
    """티커를 기반으로 자산군을 판별합니다."""
    if ticker.endswith(".KS") or ticker.endswith(".KQ"):
        return "KR_STOCK"
    return "US_STOCK"

def get_ticker_name(ticker: str) -> str:
    """yfinance를 통해 종목명(shortName)을 가져옵니다."""
    try:
        yf_ticker = yf.Ticker(ticker)
        info = yf_ticker.info
        return info.get('shortName', ticker)
    except Exception:
        return ticker

def get_asset_news(ticker: str, name: str) -> str:
    """자산군에 따라 최적화된 방식으로 뉴스를 검색합니다."""
    asset_type = get_asset_type(ticker)
    print(f"🔍 [{ticker}] 뉴스 검색 중... (Type: {asset_type})")
    
    news_text = ""
    
    if asset_type == "KR_STOCK":
        # 1. English Search (Global View)
        query_en = f"{ticker} {name} stock news"
        print(f"   👉 Query(Global): {query_en}")
        response_en = tavily_client.search(query=query_en, search_depth="advanced", max_results=3, days=1, topic="news", include_raw_content=False)
        for idx, result in enumerate(response_en['results']):
            news_text += f"\n--- [Global/English] 기사 {idx+1} ---\n"
            news_text += f"Title: {result['title']}\n"
            news_text += f"Content: {result['content']}\n"
            
        # 2. Korean Search (Local View)
        query_kr = f"{ticker} {name} 주식 뉴스"
        print(f"   👉 Query(Local): {query_kr}")
        response_kr = tavily_client.search(query=query_kr, search_depth="advanced", max_results=3, days=1, topic="news", include_raw_content=False)
        for idx, result in enumerate(response_kr['results']):
            news_text += f"\n--- [Local/Korean] 기사 {idx+1} ---\n"
            news_text += f"제목: {result['title']}\n"
            news_text += f"내용: {result['content']}\n"
            
    else:
        # US Stock
        query = f"{ticker} {name} stock news"
        print(f"   👉 Query: {query}")
        response = tavily_client.search(query=query, search_depth="advanced", max_results=5, days=1, topic="news", include_raw_content=False)
        for idx, result in enumerate(response['results']):
            news_text += f"\n--- 기사 {idx+1} ---\n"
            news_text += f"Title: {result['title']}\n"
            news_text += f"Content: {result['content']}\n"
    
    return news_text

def summarize_news(ticker: str, news_data: str) -> str:
    """Gemini API를 이용해 뉴스를 투자자 관점에서 3줄 요약합니다."""
    print(f"🧠 [{ticker}] Gemini가 뉴스를 분석 및 요약 중...\n")
    
    # 자산군에 따른 프롬프트 선택
    asset_type = get_asset_type(ticker)
    system_instruction = SYSTEM_PROMPTS.get(asset_type, SYSTEM_PROMPTS["US_STOCK"])
    
    if asset_type == "KR_STOCK":
        prompt = f"다음은 '{ticker}'에 대한 오늘자 뉴스들이다. 외신과 국내 뉴스를 구분하여 각각 3줄씩 요약해줘.\n{news_data}"
    else:
        prompt = f"다음은 '{ticker}'에 대한 오늘자 뉴스들이다. 이를 분석해서 3줄로 브리핑해줘.\n{news_data}"
    
    # 모델 호출 (temperature를 낮춰서 할루시네이션을 줄이고 팩트 위주로 생성)
    response = gemini_client.models.generate_content(
        model='gemini-2.5-flash',
        contents=prompt,
        config=types.GenerateContentConfig(
            system_instruction=system_instruction,
            temperature=0.2 
        )
    )
    
    return response.text

def get_market_data(ticker: str) -> str:
    """yfinance를 이용해 현재가 및 변동률 정보를 가져옵니다."""
    try:
        yf_ticker = ticker
        obj = yf.Ticker(yf_ticker)
        # 1달치 데이터 조회
        hist = obj.history(period="1mo")
        
        if hist.empty:
            return "⚠️ 시장 데이터 수집 실패"
        
        current_price = hist['Close'].iloc[-1]
        
        # 전일 대비 변동률 (1D)
        if len(hist) >= 2:
            prev_close = hist['Close'].iloc[-2]
            daily_change = ((current_price - prev_close) / prev_close) * 100
            daily_str = f"{daily_change:+.2f}%"
        else:
            daily_str = "-"
            
        # 30일 전 대비 변동률 (1M)
        if len(hist) > 0:
            month_ago_price = hist['Close'].iloc[0]
            month_change = ((current_price - month_ago_price) / month_ago_price) * 100
            month_str = f"{month_change:+.2f}%"
        else:
            month_str = "-"

        # 통화 및 포맷팅
        currency = "KRW" if ticker.endswith(".KS") or ticker.endswith(".KQ") else "USD"
        price_fmt = f"{current_price:,.0f}" if currency == "KRW" else f"{current_price:,.2f}"
        
        return f"💰 Price: {price_fmt} {currency} (1D: {daily_str}, 1M: {month_str})"
        
    except Exception as e:
        print(f"⚠️ Market Data Error ({ticker}): {e}")
        return ""

async def send_telegram_message(message: str):
    """텔레그램 봇을 통해 메시지를 전송합니다."""
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")

    if token and chat_id:
        bot = Bot(token=token)
        await bot.send_message(chat_id=chat_id, text=message)
    else:
        print("⚠️ 텔레그램 설정(TOKEN, CHAT_ID)이 없어 메시지를 보내지 않습니다.")

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

            # 4. 텔레그램 전송
            await send_telegram_message(result_msg)
            
        except Exception as e:
            print(f"❌ [{ticker}] 에러가 발생했습니다: {e}\n")

if __name__ == "__main__":
    asyncio.run(main())