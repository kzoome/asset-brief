import os
from datetime import datetime, timedelta
import yfinance as yf
from tavily import TavilyClient
from utils.market import get_asset_type, get_ticker_name_kr, get_ticker_name

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


def _get_yfinance_news(ticker: str, max_items: int = 5, days: int = 2) -> str:
    """yfinance를 이용해 Yahoo Finance가 큐레이팅한 뉴스를 가져옵니다.
    days 이내의 최신 기사만 포함합니다."""
    try:
        obj = yf.Ticker(ticker)
        news_items = obj.news or []
        if not news_items:
            return ""

        # 티커 및 회사명 키워드 목록 (제목 기반 관련성 필터)
        import re as _re
        try:
            info = obj.info
            name = info.get("shortName", "") or info.get("longName", "") or ""
        except Exception:
            name = ""  # ETF 등 펀더멘털 데이터 없는 종목은 종목명 키워드 없이 진행
        keywords = [ticker.split(".")[0].lower()]
        for word in name.split():
            clean = _re.sub(r'[^a-zA-Z0-9가-힣]', '', word).lower()
            if len(clean) >= 3:  # 짧은 단어(Inc, Co 등) 제외
                keywords.append(clean)

        cutoff = datetime.now() - timedelta(days=days)

        news_text = ""
        count = 0
        skipped_old = 0
        for item in news_items:
            # yfinance 최신 API 구조 (item['content'] 내부에 데이터 존재) 및 구형 구조 모두 대응
            content_dict = item.get("content", item) if isinstance(item.get("content"), dict) else item

            title = content_dict.get("title", item.get("title", ""))

            # 날짜 필터링: pubDate가 있으면 cutoff 이전 기사 제외
            pub_date_str = content_dict.get("pubDate", "") or content_dict.get("displayTime", "") or item.get("pubDate", "")
            if pub_date_str:
                try:
                    pub_dt = datetime.fromisoformat(pub_date_str.replace("Z", "+00:00")).replace(tzinfo=None)
                    if pub_dt < cutoff:
                        skipped_old += 1
                        continue
                except (ValueError, TypeError):
                    pass

            provider = content_dict.get("provider", {})
            if not isinstance(provider, dict):
                provider = {}
            publisher = provider.get("displayName", item.get("publisher", ""))

            link = ""
            click_through = content_dict.get("clickThroughUrl", {})
            if isinstance(click_through, dict):
                link = click_through.get("url", "")
            if not link:
                link = content_dict.get("canonicalUrl", {}).get("url", "") if isinstance(content_dict.get("canonicalUrl"), dict) else ""
            if not link:
                link = item.get("link", "")

            if not title:
                continue

            # 제목에 티커 또는 회사명 키워드가 없으면 무관한 기사로 판단하여 건너뜀
            title_lower = title.lower()
            if not any(kw in title_lower for kw in keywords):
                continue

            news_text += f"\n--- [Yahoo Finance] 기사 {count+1} ---\n"
            news_text += f"Title: {title}\n"
            if link:
                news_text += f"{publisher} {link}\n"
            else:
                news_text += f"{publisher}\n"
            count += 1
            if count >= max_items:
                break

        if skipped_old > 0:
            print(f"   🗓️ yfinance 오래된 기사 {skipped_old}건 제외 ({days}일 기준)")

        return news_text
    except Exception as e:
        print(f"   ⚠️ yfinance 뉴스 수집 실패 ({ticker}): {e}")
        return ""


def _search_tavily(query: str, include_domains: list, max_results: int = 5,
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


def fetch_google_news(query: str, max_results: int = 5, days: int = 1) -> list:
    """Google News RSS를 통해 기사를 가져옵니다. Tavily 검색 실패 시 대안으로 사용합니다."""
    import urllib.parse
    import feedparser
    import ssl
    
    enc_query = urllib.parse.quote(query)
    # 한국어 뉴스 검색
    url = f"https://news.google.com/rss/search?q={enc_query}&hl=ko&gl=KR&ceid=KR:ko"
    
    if hasattr(ssl, '_create_unverified_context'):
        ssl._create_default_https_context = ssl._create_unverified_context
        
    try:
        feed = feedparser.parse(url)
        cutoff = datetime.now() - timedelta(days=days + 1)
        results = []
        
        for entry in feed.entries:
            pub_date_str = entry.get('published', '')
            if pub_date_str:
                try:
                    parsed_dt = datetime(*entry.published_parsed[:6])
                    if parsed_dt < cutoff:
                        continue
                except Exception:
                    pass
            
            # Google RSS는 content 전문이 없으므로 summary(미리보기)를 대신 사용
            results.append({
                "title": entry.title,
                "url": entry.link,
                "content": entry.get('summary', ''),
                "published_date": pub_date_str
            })
            if len(results) >= max_results:
                break
        return results
    except Exception as e:
        print(f"   ⚠️ Google News RSS 수집 실패: {e}")
        return []

def fetch_naver_news(query: str, max_results: int = 5, days: int = 1) -> list:
    """Naver News 검색 API를 통해 최신 기사를 가져옵니다."""
    import urllib.parse
    import urllib.request
    import json
    from email.utils import parsedate_to_datetime
    
    client_id = os.getenv("NAVER_CLIENT_ID")
    client_secret = os.getenv("NAVER_SECRET_KEY")
    
    if not client_id or not client_secret:
        return []
        
    enc_query = urllib.parse.quote(query)
    # sort=date로 변경하여 최신순 수집
    url = f"https://openapi.naver.com/v1/search/news.json?query={enc_query}&display=100&sort=date"
    
    request = urllib.request.Request(url)
    request.add_header("X-Naver-Client-Id", client_id)
    request.add_header("X-Naver-Client-Secret", client_secret)
    
    try:
        response = urllib.request.urlopen(request)
        if response.getcode() == 200:
            data = json.loads(response.read().decode('utf-8'))
            from bs4 import BeautifulSoup

            now = datetime.now()
            cutoff = now - timedelta(days=days + 1)  # Tavily/Google과 동일하게 여유 +1일
            priority_cutoff = now - timedelta(hours=24)  # 24시간 이내 = 우선순위 높음

            candidates = []
            for item in data.get('items', []):
                pub_date_str = item.get('pubDate', '')
                pub_dt = None
                if pub_date_str:
                    try:
                        pub_dt = parsedate_to_datetime(pub_date_str).replace(tzinfo=None)
                        if pub_dt < cutoff:
                            continue
                    except Exception:
                        pass

                title = BeautifulSoup(item.get('title', ''), "html.parser").get_text()
                desc = BeautifulSoup(item.get('description', ''), "html.parser").get_text()

                # 24시간 이내면 우선순위 0, 그 이상이면 1 (낮을수록 먼저)
                priority = 0 if (pub_dt and pub_dt >= priority_cutoff) else 1

                candidates.append({
                    "title": title,
                    "url": item.get('link', ''),
                    "content": desc,
                    "published_date": pub_date_str,
                    "_priority": priority,
                    "_pub_dt": pub_dt or datetime.min,
                })

            # 24시간 이내 기사 먼저, 그 다음 최신순
            candidates.sort(key=lambda x: (x["_priority"], -x["_pub_dt"].timestamp()))

            results = []
            for c in candidates[:max_results]:
                results.append({k: v for k, v in c.items() if not k.startswith("_")})

            dropped = len(data.get('items', [])) - len(candidates)
            if dropped > 0:
                print(f"   🔻 Naver 뉴스 필터링: {dropped}건 제외 (오래된 기사)")

            return results
    except Exception as e:
        print(f"   ⚠️ Naver News API 수집 실패: {e}")
    return []

def get_asset_news(ticker: str, name: str, etf_queries: dict | None = None) -> str:
    """자산군에 따라 최적화된 방식으로 뉴스를 검색합니다.

    전략:
    - 공통: yfinance 뉴스 (무료, Yahoo Finance 큐레이팅)
    - Tavily: basic 검색(1크레딧/건)
      - 미국: 영미권 신뢰 매체, 종목당 1회
      - 한국: 글로벌 영문 매체(외신) + 국내 경제지, 종목당 2회
    - ETF: etf_queries로 테마/섹터 기반 검색어 사용
    """
    asset_type = get_asset_type(ticker)
    etf_tag = " [ETF]" if etf_queries else ""
    print(f"🔍 [{ticker}] 뉴스 검색 중... (Type: {asset_type}{etf_tag})")

    news_text = ""

    # ── 공통: yfinance 뉴스 ──
    yf_news = _get_yfinance_news(ticker)
    if yf_news:
        news_text += yf_news

    # ── Tavily 검색 ──
    if asset_type == "KR_STOCK":
        # 1) 글로벌 외신 검색어 결정
        if etf_queries:
            query_global = etf_queries["english_query"]
        else:
            query_global = KR_GLOBAL_QUERY_MAP.get(ticker, get_ticker_name(ticker))
        print(f"   👉 Query(Global): {query_global}")
        etf_min_score = 0.35 if etf_queries else 0.03
        results_global = _search_tavily(query_global, TRUSTED_DOMAINS_US,
                                        max_results=5, min_score=etf_min_score)
        for idx, result in enumerate(results_global):
            news_text += f"\n--- [Global/English] 기사 {idx+1} ---\n"
            news_text += f"Title: {result['title']}\n"
            news_text += f"Content: {result['content']}\n"
            if result.get('url'):
                news_text += f"Source: {result['url']}\n"

        # 2) 국내 뉴스 검색어 결정
        if etf_queries and etf_queries.get("korean_query"):
            query_local = etf_queries["korean_query"]
        else:
            query_local = name
        print(f"   👉 Query(Local): {query_local}")

        results = []
        results_naver = fetch_naver_news(query_local, max_results=5)
        if results_naver:
            print(f"   ✅ Naver News API 수집 완료 ({len(results_naver)}건)")
            results.extend(results_naver)

        results_google = fetch_google_news(query_local, max_results=5, days=1)
        if results_google:
            print(f"   ✅ Google News RSS 수집 완료 ({len(results_google)}건)")
            results.extend(results_google)

        if not results:
            print(f"   ⚠️ Naver 및 Google News RSS 검색 결과 없음. Tavily로 대체 수집 🚀")
            results = _search_tavily(query_local, TRUSTED_DOMAINS_KR, max_results=5)

        for idx, result in enumerate(results):
            news_text += f"\n--- [Local/Korean] 기사 {idx+1} ---\n"
            news_text += f"제목: {result['title']}\n"
            news_text += f"내용: {result['content']}\n"
            if result.get('url'):
                news_text += f"Source: {result['url']}\n"

    else:
        # US Stock / US ETF
        if etf_queries:
            query = etf_queries["english_query"]
        else:
            import re
            clean_name = re.sub(r'(?i)\b(inc|corp|corporation|co|ltd|plc|company|holdings?|group|international|limited)\b\.?', '', name).strip()
            clean_name = re.sub(r'[,]+', '', clean_name).strip()
            clean_name = re.sub(r'\s+', ' ', clean_name)
            if not clean_name:
                clean_name = name.split()[0]
            query = f'{ticker} OR "{clean_name}"'
        print(f"   👉 Query: {query}")

        results = _search_tavily(query, TRUSTED_DOMAINS_US, max_results=5)

        if not results:
            results = fetch_google_news(query, max_results=5, days=1)
            if results:
                print(f"   ✅ Google News RSS 폴백 수집 완료 ({len(results)}건)")

        for idx, result in enumerate(results):
            news_text += f"\n--- 기사 {idx+1} ---\n"
            news_text += f"Title: {result['title']}\n"
            news_text += f"Content: {result['content']}\n"
            if result.get('url'):
                news_text += f"Source: {result['url']}\n"

    if not news_text.strip():
        news_text = "⚠️ 수집된 뉴스가 없습니다."

    return news_text

def get_market_news(market: str = "all") -> str:
    """전반적인 시장 뉴스(시황)를 수집합니다."""
    queries = []
    if market == "us":
        queries.append("US Stock Market Today")
    elif market == "kr":
        queries.append("국내 증시 시황 전망")
    else:
        queries.append("Global Stock Market News")
        queries.append("국내 증시 시황")

    news_text = ""
    for query in queries:
        print(f"🌍 시장 뉴스 검색 중: {query}")
        # Tavily (1 credit)
        results = _search_tavily(query, include_domains=None, max_results=7, days=1)
        
        # Fallback to Google News if empty
        if not results:
            results = fetch_google_news(query, max_results=7, days=1)
            
        for idx, r in enumerate(results):
            news_text += f"\n- {r['title']}\n  Content: {r['content'][:200]}...\n"
            if r.get('url'):
                news_text += f"  Source: {r['url']}\n"
    
    return news_text
