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
