import os
from tavily import TavilyClient
from utils.market import get_asset_type

# main.py에서 load_dotenv()가 선행되므로 이 시점에 환경변수 로딩 가능
tavily_api_key = os.getenv("TAVILY_API_KEY")
tavily_client = TavilyClient(api_key=tavily_api_key) if tavily_api_key else None

def get_asset_news(ticker: str, name: str) -> str:
    """자산군에 따라 최적화된 방식으로 뉴스를 검색합니다."""
    if not tavily_client:
        return "⚠️ Tavily API 설정이 누락되어 뉴스를 가져올 수 없습니다."
        
    asset_type = get_asset_type(ticker)
    print(f"🔍 [{ticker}] 뉴스 검색 중... (Type: {asset_type})")
    
    news_text = ""
    
    if asset_type == "KR_STOCK":
        # 1. English Search (Global View)
        query_en = f"{ticker} {name} stock news"
        print(f"   👉 Query(Global): {query_en}")
        response_en = tavily_client.search(query=query_en, search_depth="advanced", max_results=3, days=1, topic="news", include_raw_content=False)
        for idx, result in enumerate(response_en.get('results', [])):
            news_text += f"\n--- [Global/English] 기사 {idx+1} ---\n"
            news_text += f"Title: {result['title']}\n"
            news_text += f"Content: {result['content']}\n"
            
        # 2. Korean Search (Local View)
        query_kr = f"{ticker} {name} 주식 뉴스"
        print(f"   👉 Query(Local): {query_kr}")
        response_kr = tavily_client.search(query=query_kr, search_depth="advanced", max_results=3, days=1, topic="news", include_raw_content=False)
        for idx, result in enumerate(response_kr.get('results', [])):
            news_text += f"\n--- [Local/Korean] 기사 {idx+1} ---\n"
            news_text += f"제목: {result['title']}\n"
            news_text += f"내용: {result['content']}\n"
            
    else:
        # US Stock
        query = f"{ticker} {name} stock news"
        print(f"   👉 Query: {query}")
        response = tavily_client.search(query=query, search_depth="advanced", max_results=5, days=1, topic="news", include_raw_content=False)
        for idx, result in enumerate(response.get('results', [])):
            news_text += f"\n--- 기사 {idx+1} ---\n"
            news_text += f"Title: {result['title']}\n"
            news_text += f"Content: {result['content']}\n"
    
    return news_text
