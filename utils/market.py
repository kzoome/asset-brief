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
    """yfinance를 이용해 현재가 및 다기간 변동률 정보를 가져옵니다."""
    try:
        yf_ticker = ticker
        obj = yf.Ticker(yf_ticker)
        # 2년치 데이터 조회 (1Y 변동률 계산 시 누락 방지)
        hist = obj.history(period="2y")
        
        if hist.empty:
            return "⚠️ 시장 데이터 수집 실패"
        
        current_price = hist['Close'].iloc[-1]
        
        def get_change(days_ago):
            if len(hist) > days_ago:
                old_val = hist['Close'].iloc[-days_ago-1]
                return ((current_price - old_val) / old_val) * 100
            return None

        # 변동률 계산 (영업일 기준 근사치)
        d1 = get_change(1)   # 1D
        m1 = get_change(21)  # 1M (약 21영업일)
        m3 = get_change(63)  # 3M (약 63영업일)
        m6 = get_change(126) # 6M (약 126영업일)
        y1 = get_change(252) # 1Y (약 252영업일)

        def fmt_chg(val):
            return f"{val:+.2f}%" if val is not None else "-"

        # 통화 및 포맷팅
        currency = "KRW" if ticker.endswith(".KS") or ticker.endswith(".KQ") else "USD"
        price_fmt = f"{current_price:,.0f}" if currency == "KRW" else f"{current_price:,.2f}"
        
        return (f"💰 Price: {price_fmt} {currency} "
                f"(1D: {fmt_chg(d1)}, 1M: {fmt_chg(m1)}, 3M: {fmt_chg(m3)}, 6M: {fmt_chg(m6)}, 1Y: {fmt_chg(y1)})")
        
    except Exception as e:
        print(f"⚠️ Market Data Error ({ticker}): {e}")
        return ""

def get_global_market_status(market: str = "all") -> str:
    """주요 시장 지수 및 환율 정보를 가져옵니다 (다기간 변동률 포함)."""
    indices = []
    if market in ["us", "all"]:
        indices += [("^GSPC", "S&P 500"), ("^IXIC", "Nasdaq"), ("^DJI", "Dow Jones")]
    if market in ["kr", "all"]:
        indices += [("^KS11", "KOSPI"), ("^KQ11", "KOSDAQ")]
    
    indices += [("USDKRW=X", "USD/KRW")]

    results = []
    for ticker, label in indices:
        try:
            obj = yf.Ticker(ticker)
            hist = obj.history(period="2y")
            if hist.empty: continue
            
            curr = hist['Close'].iloc[-1]
            
            def get_chg(days):
                if len(hist) > days:
                    old = hist['Close'].iloc[-days-1]
                    val = ((curr - old) / old) * 100
                    return f"{val:+.1f}%"
                return "-"

            d1 = get_chg(1)
            m1 = get_chg(21)
            m3 = get_chg(63)
            y1 = get_chg(252)
            
            val_fmt = f"{curr:,.2f}" if ticker != "USDKRW=X" else f"{curr:,.1f}"
            results.append(f"• {label}: {val_fmt} (1D: {d1}, 1M: {m1}, 3M: {m3}, 1Y: {y1})")
        except Exception:
            continue
            
    return "\n".join(results)
