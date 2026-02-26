import os
import yfinance as yf
from tavily import TavilyClient
from utils.market import get_asset_type, get_ticker_name_kr

# main.py에서 load_dotenv()가 선행되므로 이 시점에 환경변수 로딩 가능
tavily_api_key = os.getenv("TAVILY_API_KEY")
tavily_client = TavilyClient(api_key=tavily_api_key) if tavily_api_key else None

# ─── 신뢰할 수 있는 도메인 목록 ───
TRUSTED_DOMAINS_US = [
    "reuters.com",
    "bloomberg.com",
    "cnbc.com",
    "wsj.com",
    "ft.com",
    "seekingalpha.com",
    "marketwatch.com",
    "barrons.com",
    "finance.yahoo.com",
]

# 국내 종목은 국내 언론사만 사용 (yfinance가 외신 역할 담당)
TRUSTED_DOMAINS_KR = [
    "hankyung.com",
    "mk.co.kr",
    "sedaily.com",
    "edaily.co.kr",
    "etnews.com",
    "mt.co.kr",
    "biz.chosun.com",
    "thebell.co.kr",
]

EXCLUDE_DOMAINS = [
    "tistory.com",
    "naver.com",
    "blog.naver.com",
    "cafe.naver.com",
    "reddit.com",
    "youtube.com",
]

# 시세/마켓 인덱스 페이지 제목 필터
EXCLUDE_TITLE_PATTERNS = [
    "시장종합", "시세", "차트", "종목 상세",
    "stock quote", "stock price",
]


def _get_yfinance_news(ticker: str, max_items: int = 5) -> str:
    """yfinance를 이용해 Yahoo Finance가 큐레이팅한 뉴스를 가져옵니다."""
    try:
        obj = yf.Ticker(ticker)
        news_items = obj.news or []
        if not news_items:
            return ""

        news_text = ""
        count = 0
        for item in news_items:
            title = item.get("title", "")
            publisher = item.get("publisher", "")
            if not title:
                continue
            news_text += f"\n--- [Yahoo Finance] 기사 {count+1} ---\n"
            news_text += f"Title: {title}\n"
            news_text += f"Source: {publisher}\n"
            count += 1
            if count >= max_items:
                break
        return news_text
    except Exception as e:
        print(f"   ⚠️ yfinance 뉴스 수집 실패 ({ticker}): {e}")
        return ""


def _search_tavily(query: str, include_domains: list, max_results: int = 3,
                   days: int = 1, min_score: float = 0.1) -> list:
    """Tavily basic 검색을 도메인 필터링과 함께 수행합니다. (1 크레딧/건)"""
    if not tavily_client:
        return []
    try:
        response = tavily_client.search(
            query=query,
            search_depth="basic",          # advanced(2크레딧) → basic(1크레딧)
            max_results=max_results,
            days=days,
            topic="news",
            include_raw_content=False,
            include_domains=include_domains,
            exclude_domains=EXCLUDE_DOMAINS,
        )
        results = response.get("results", [])

        # 1. score 필터
        filtered = [r for r in results if r.get("score", 0) >= min_score]
        # 2. 시세 페이지 제목 필터
        filtered = [
            r for r in filtered
            if not any(pat in r.get("title", "") for pat in EXCLUDE_TITLE_PATTERNS)
        ]
        # 3. 중복 제거
        seen = set()
        deduped = []
        for r in filtered:
            title = r.get("title", "")
            if title not in seen:
                seen.add(title)
                deduped.append(r)
        # 4. score 내림차순 정렬
        deduped.sort(key=lambda r: r.get("score", 0), reverse=True)

        dropped = len(results) - len(deduped)
        if dropped > 0:
            print(f"   🔻 필터링: {dropped}건 제외")
        return deduped
    except Exception as e:
        print(f"   ⚠️ Tavily 검색 오류: {e}")
        return []


def get_asset_news(ticker: str, name: str) -> str:
    """자산군에 따라 최적화된 방식으로 뉴스를 검색합니다.

    전략:
    - 공통: yfinance 뉴스 (무료, Yahoo Finance 큐레이팅) — 외신 역할
    - Tavily: basic 검색(1크레딧/건), 종목당 1회 호출
      - 미국: 영미권 신뢰 매체
      - 한국: 국내 경제지 (외신은 yfinance로 대체)
    """
    asset_type = get_asset_type(ticker)
    print(f"🔍 [{ticker}] 뉴스 검색 중... (Type: {asset_type})")

    news_text = ""

    # ── 공통: yfinance 뉴스 ──
    yf_news = _get_yfinance_news(ticker)
    if yf_news:
        news_text += yf_news

    # ── Tavily: 종목당 1회만 호출 ──
    if asset_type == "KR_STOCK":
        name_kr = get_ticker_name_kr(ticker)
        query = name_kr          # 한글명만으로 검색
        print(f"   👉 Query(Local): {query}")
        results = _search_tavily(query, TRUSTED_DOMAINS_KR, max_results=3)
        for idx, result in enumerate(results):
            news_text += f"\n--- [Local/Korean] 기사 {idx+1} ---\n"
            news_text += f"제목: {result['title']}\n"
            news_text += f"내용: {result['content']}\n"

    else:
        # US Stock: 티커 + 첫 단어로 검색
        query = f"{ticker} {name.split()[0]}"
        print(f"   👉 Query: {query}")
        results = _search_tavily(query, TRUSTED_DOMAINS_US, max_results=3)
        for idx, result in enumerate(results):
            news_text += f"\n--- 기사 {idx+1} ---\n"
            news_text += f"Title: {result['title']}\n"
            news_text += f"Content: {result['content']}\n"

    if not news_text.strip():
        news_text = "⚠️ 수집된 뉴스가 없습니다."

    return news_text
