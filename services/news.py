import os
from datetime import datetime, timedelta
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

# 한국 종목의 글로벌 외신 검색용 영문 키워드 (yfinance shortName + 산업 키워드)
KR_GLOBAL_QUERY_MAP = {
    "000660.KS": "SK hynix memory HBM",
    "003230.KS": "Samyang Foods ramen",
    "009540.KS": "HD Korea Shipbuilding",
    "352820.KS": "HYBE K-pop",
    "138040.KS": "Meritz Financial",
    "298040.KS": "Hyosung Heavy Industries transformer",
    "017670.KS": "SK Telecom AI",
    "005930.KS": "Samsung Electronics semiconductor",
    "373220.KS": "LG Energy Solution battery",
}


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
            # yfinance 뉴스 링크 추출
            link = ""
            content = item.get("content", {})
            if isinstance(content, dict):
                link = content.get("clickThroughUrl", {}).get("url", "")
            if not link:
                link = item.get("link", "")
            if not title:
                continue
            news_text += f"\n--- [Yahoo Finance] 기사 {count+1} ---\n"
            news_text += f"Title: {title}\n"
            news_text += f"Source: {publisher}\n"
            if link:
                news_text += f"URL: {link}\n"
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
        # 2. 날짜 필터: published_date가 있으면 days 범위 내인지 확인, 없으면 URL에서 추정, 그래도 없으면 HTML 확인
        cutoff = datetime.now() - timedelta(days=days + 1)  # 여유 +1일
        date_filtered = []
        import re
        import urllib.request
        
        for r in filtered:
            pub = r.get("published_date", "")
            pub_dt = None
            
            # (1) published_date 파싱 시도
            if pub:
                try:
                    pub_dt = datetime.fromisoformat(pub.replace("Z", "+00:00")).replace(tzinfo=None)
                except (ValueError, TypeError):
                    pass
            
            # (2) 실패 시 URL에서 날짜 추출 시도 (예: 2026/02/12 또는 20260212)
            url = r.get("url", "")
            if not pub_dt and url:
                match = re.search(r'(20[12]\d)[-/]?([01]\d)[-/]?([0-3]\d)', url)
                if match:
                    try:
                        year, month, day = map(int, match.groups())
                        pub_dt = datetime(year, month, day)
                    except ValueError:
                        pass
                        
            # (3) 그래도 실패 시 HTML 콘텐츠 일부를 다운로드하여 날짜 패턴 탐색
            if not pub_dt and url:
                try:
                    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
                    with urllib.request.urlopen(req, timeout=3) as response:
                        html = response.read(20000).decode('utf-8', errors='ignore') # 앞부분 20KB만 확인
                        
                        # meta 태그 등에서 날짜 추출 우선 시도
                        meta_match = re.search(r'<meta[^>]*property=["\']article:published_time["\'][^>]*content=["\']([^"\']+)["\']', html)
                        if meta_match:
                            try:
                                pub_dt = datetime.fromisoformat(meta_match.group(1).replace("Z", "+00:00")).replace(tzinfo=None)
                            except ValueError:
                                pass
                        
                        # meta 실패 시 HTML 텍스트에서 일반적인 YYYY-MM-DD 또는 YYYY.MM.DD 패턴 탐색
                        if not pub_dt:
                            date_match = re.search(r'(20[12]\d)[-/.]([01]\d)[-/.]([0-3]\d)', html)
                            if date_match:
                                try:
                                    y, m, d = map(int, date_match.groups())
                                    pub_dt = datetime(y, m, d)
                                except ValueError:
                                    pass
                except Exception as e:
                    print(f"   ⚠️ HTML 날짜 추출 실패 ({url}): {e}")
            
            # (4) 날짜가 존재하고 cutoff 이전이면 제외
            if pub_dt:
                if pub_dt < cutoff:
                    print(f"   🗓️ 오래된 기사 제외: {r.get('title', '')[:40]}... ({pub_dt.strftime('%Y-%m-%d')})")
                    continue
            else:
                # 끝까지 날짜를 모르는 경우 제외 (오래된 기사 노출 방지 위함)
                print(f"   🗓️ 날짜 미상 기사 제외: {r.get('title', '')[:40]}...")
                continue
            
            date_filtered.append(r)
        filtered = date_filtered
        # 3. 시세 페이지 제목 필터
        filtered = [
            r for r in filtered
            if not any(pat in r.get("title", "") for pat in EXCLUDE_TITLE_PATTERNS)
        ]
        # 4. 중복 제거
        seen = set()
        deduped = []
        for r in filtered:
            title = r.get("title", "")
            if title not in seen:
                seen.add(title)
                deduped.append(r)
        # 5. score 내림차순 정렬
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
    - 공통: yfinance 뉴스 (무료, Yahoo Finance 큐레이팅)
    - Tavily: basic 검색(1크레딧/건)
      - 미국: 영미권 신뢰 매체, 종목당 1회
      - 한국: 글로벌 영문 매체(외신) + 국내 경제지, 종목당 2회
    """
    asset_type = get_asset_type(ticker)
    print(f"🔍 [{ticker}] 뉴스 검색 중... (Type: {asset_type})")

    news_text = ""

    # ── 공통: yfinance 뉴스 ──
    yf_news = _get_yfinance_news(ticker)
    if yf_news:
        news_text += yf_news

    # ── Tavily 검색 ──
    if asset_type == "KR_STOCK":
        # 1) 글로벌 외신: 최적화된 영문 키워드로 영미권 매체 검색
        #    (신뢰 도메인 한정이므로 min_score를 낮춰도 노이즈가 적음)
        query_global = KR_GLOBAL_QUERY_MAP.get(ticker, name)
        print(f"   👉 Query(Global): {query_global}")
        results_global = _search_tavily(query_global, TRUSTED_DOMAINS_US,
                                        max_results=3, min_score=0.03)
        for idx, result in enumerate(results_global):
            news_text += f"\n--- [Global/English] 기사 {idx+1} ---\n"
            news_text += f"Title: {result['title']}\n"
            news_text += f"Content: {result['content']}\n"
            if result.get('url'):
                news_text += f"URL: {result['url']}\n"

        # 2) 국내 뉴스: 한글명으로 국내 경제지 검색
        name_kr = get_ticker_name_kr(ticker)
        query = name_kr          # 한글명만으로 검색
        print(f"   👉 Query(Local): {query}")
        results = _search_tavily(query, TRUSTED_DOMAINS_KR, max_results=3)
        for idx, result in enumerate(results):
            news_text += f"\n--- [Local/Korean] 기사 {idx+1} ---\n"
            news_text += f"제목: {result['title']}\n"
            news_text += f"내용: {result['content']}\n"
            if result.get('url'):
                news_text += f"URL: {result['url']}\n"

    else:
        # US Stock: 티커 + 첫 단어로 검색
        query = f"{ticker} {name.split()[0]}"
        print(f"   👉 Query: {query}")
        results = _search_tavily(query, TRUSTED_DOMAINS_US, max_results=3)
        for idx, result in enumerate(results):
            news_text += f"\n--- 기사 {idx+1} ---\n"
            news_text += f"Title: {result['title']}\n"
            news_text += f"Content: {result['content']}\n"
            if result.get('url'):
                news_text += f"URL: {result['url']}\n"

    if not news_text.strip():
        news_text = "⚠️ 수집된 뉴스가 없습니다."

    return news_text
