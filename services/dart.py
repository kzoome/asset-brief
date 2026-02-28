import os
from datetime import datetime, timedelta
import OpenDartReader

def get_recent_disclosures(ticker: str, days: int = 2) -> str:
    """
    주어진 티커(종목코드)에 대해 최근 N일간의 DART 공시 목록을 가져옵니다.
    """
    api_key = os.getenv("DART_API_KEY")
    if not api_key:
        return ""

    try:
        dart = OpenDartReader(api_key)
        
        # OpenDartReader는 yfinance의 '005930.KS' 포맷에서 .KS 등을 떼어내고 사용해야 함
        clean_ticker = ticker.split('.')[0]
        
        # 기준일 계산 (오늘 기준으로 며칠 전부터)
        start_date = (datetime.now() - timedelta(days=days)).strftime('%Y%m%d')
        
        # 공시 검색 (티커 기반)
        # res는 DataFrame 형태로 반환됨
        res = dart.list(clean_ticker, start=start_date)
        
        if res is None or res.empty:
            return ""

        # 최신 공시부터 상위 5개만 텍스트로 정리
        max_items = 5
        disclosure_text = "\n[📊 최근 DART 공시]\n"
        count = 0
        
        for idx, row in res.iterrows():
            date_str = row['rcept_dt']
            # 보기 편하게 날짜 포맷 변경 (YYYYMMDD -> YYYY-MM-DD)
            formatted_date = f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:]}"
            title = row['report_nm']
            
            # 접수 번호로 URL 생성 (DART 뷰어)
            rcept_no = row['rcept_no']
            url = f"https://dart.fss.or.kr/dsaf001/main.do?rcpNo={rcept_no}"
            
            disclosure_text += f"- [{formatted_date}] {title} (링크: {url})\n"
            
            count += 1
            if count >= max_items:
                break
                
        return disclosure_text
        
    except Exception as e:
        print(f"   ⚠️ DART 공시 수집 실패 ({ticker}): {e}")
        return ""
