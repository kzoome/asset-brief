import yfinance as yf

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

# 국내 종목 한글명 매핑 (yfinance는 한글명을 제공하지 않으므로 직접 관리)
KR_TICKER_NAME_MAP = {
    # 사용자 보유 종목
    "003230.KS": "삼양식품",
    "009540.KS": "HD한국조선해양",
    "352820.KS": "하이브",
    "000660.KS": "SK하이닉스",
    "138040.KS": "메리츠금융지주",
    "298040.KS": "효성중공업",
    "017670.KS": "SK텔레콤",
    # 기타 주요 종목 (필요 시 추가)
    "005930.KS": "삼성전자",
    "035420.KS": "네이버",
    "035720.KS": "카카오",
    "051910.KS": "LG화학",
    "006400.KS": "삼성SDI",
    "105560.KS": "KB금융",
    "055550.KS": "신한지주",
    "373220.KS": "LG에너지솔루션",
    "207940.KS": "삼성바이오로직스",
}

def get_ticker_name_kr(ticker: str) -> str:
    """국내 종목의 한글명을 반환합니다. 매핑이 없으면 영문명을 반환합니다."""
    return KR_TICKER_NAME_MAP.get(ticker, get_ticker_name(ticker))

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
