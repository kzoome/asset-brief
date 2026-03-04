import os
import re
import logging

logger = logging.getLogger(__name__)

# 폴백용 하드코딩 포트폴리오 (구글 시트 연결 실패 시 사용)
FALLBACK_PORTFOLIO = [
    {"ticker": "BRK-B",      "name": "Berkshire Hathaway", "weight": 0.0, "change_1d": 0.0, "market": "us"},
    {"ticker": "GOOGL",      "name": "Alphabet",           "weight": 0.0, "change_1d": 0.0, "market": "us"},
    {"ticker": "MSFT",       "name": "Microsoft",          "weight": 0.0, "change_1d": 0.0, "market": "us"},
    {"ticker": "TSLA",       "name": "Tesla",              "weight": 0.0, "change_1d": 0.0, "market": "us"},
    {"ticker": "AAPL",       "name": "Apple",              "weight": 0.0, "change_1d": 0.0, "market": "us"},
    {"ticker": "AVGO",       "name": "Broadcom",           "weight": 0.0, "change_1d": 0.0, "market": "us"},
    {"ticker": "003230.KS",  "name": "삼양식품",            "weight": 0.0, "change_1d": 0.0, "market": "kr"},
    {"ticker": "009540.KS",  "name": "HD한국조선해양",      "weight": 0.0, "change_1d": 0.0, "market": "kr"},
    {"ticker": "352820.KS",  "name": "하이브",              "weight": 0.0, "change_1d": 0.0, "market": "kr"},
    {"ticker": "000660.KS",  "name": "SK하이닉스",          "weight": 0.0, "change_1d": 0.0, "market": "kr"},
    {"ticker": "138040.KS",  "name": "메리츠금융지주",      "weight": 0.0, "change_1d": 0.0, "market": "kr"},
    {"ticker": "298040.KS",  "name": "효성중공업",          "weight": 0.0, "change_1d": 0.0, "market": "kr"},
    {"ticker": "017670.KS",  "name": "SK텔레콤",            "weight": 0.0, "change_1d": 0.0, "market": "kr"},
]

# 포함할 자산종류 (substring 매칭)
TARGET_ASSET_TYPES = ("국내주식", "해외주식")


def _parse_pct(value: str) -> float:
    """'12.5%', '-3.2%' 등 퍼센트 문자열을 float으로 변환합니다."""
    if not value:
        return 0.0
    cleaned = str(value).replace("%", "").replace(",", "").strip()
    try:
        return float(cleaned)
    except ValueError:
        return 0.0


def _normalize_ticker(raw: str, asset_type: str) -> tuple[str, str]:
    """
    티커를 yfinance 호환 형식으로 정규화하고 (ticker, market)을 반환합니다.
    market은 자산종류 컬럼 기준: '국내주식' → 'kr', '해외주식' → 'us'
    - 6자리 숫자 → '{ticker}.KS' (국내/해외 불문)
    - 'BRK.B' 형태 → 'BRK-B' ('.' → '-')
    - 그 외 → 원본 그대로
    """
    ticker = str(raw).strip()
    market = "kr" if "국내주식" in asset_type else "us"

    # 6자리 숫자 → 한국 거래소 상장 티커 (.KS)
    if re.match(r"^\d{6}$", ticker):
        return f"{ticker}.KS", market

    # 'XXX.X' 형태 (BRK.B 등) → 'XXX-X'
    if re.match(r"^[A-Z]+\.[A-Z]+$", ticker):
        return ticker.replace(".", "-"), market

    return ticker, market


def _is_target(asset_type: str) -> bool:
    return any(t in asset_type for t in TARGET_ASSET_TYPES)


def load_portfolio() -> list[dict]:
    """
    구글 시트에서 포트폴리오를 로드합니다.

    1단계: "종목별 현황(raw)" → {종목명: (ticker, market)} 매핑 구성
    2단계: "종목별 현황"     → 비중(E열), 변동(1d)(F열) 읽기 + 매핑 조인

    Returns:
        list of dict: [{'ticker', 'name', 'weight', 'change_1d', 'market'}, ...]
        비중 내림차순 정렬. 실패 시 FALLBACK_PORTFOLIO 반환.
    """
    try:
        import gspread
        from google.oauth2.service_account import Credentials
    except ImportError:
        logger.warning("gspread 또는 google-auth 미설치. 폴백 포트폴리오를 사용합니다.")
        return FALLBACK_PORTFOLIO

    sa_file = os.getenv(
        "GOOGLE_SERVICE_ACCOUNT_FILE",
        os.path.join(os.path.dirname(__file__), "../../asset-treemap/service_account.json"),
    )
    sa_file = os.path.abspath(sa_file)
    sheet_id = os.getenv("GOOGLE_SHEET_ID", "")

    if not sheet_id:
        logger.warning("GOOGLE_SHEET_ID 미설정. 폴백 포트폴리오를 사용합니다.")
        return FALLBACK_PORTFOLIO

    if not os.path.exists(sa_file):
        logger.warning(f"서비스 계정 파일 없음: {sa_file}. 폴백 포트폴리오를 사용합니다.")
        return FALLBACK_PORTFOLIO

    try:
        scopes = [
            "https://www.googleapis.com/auth/spreadsheets.readonly",
            "https://www.googleapis.com/auth/drive.readonly",
        ]
        creds = Credentials.from_service_account_file(sa_file, scopes=scopes)
        gc = gspread.authorize(creds)
        spreadsheet = gc.open_by_key(sheet_id)

        # ── 1단계: raw 시트에서 종목명 → (ticker, market) 매핑 구성 ──
        raw_ws = spreadsheet.worksheet("종목별 현황(raw)")
        raw_rows = raw_ws.get_all_values()

        if not raw_rows:
            logger.warning("raw 시트가 비어 있습니다. 폴백 포트폴리오를 사용합니다.")
            return FALLBACK_PORTFOLIO

        raw_header = raw_rows[0]
        raw_col = {h.strip(): i for i, h in enumerate(raw_header)}

        ticker_col = next((c for c in ("Ticker", "티커") if c in raw_col), None)
        if not ticker_col or "종목명" not in raw_col or "자산종류" not in raw_col:
            logger.warning(f"raw 시트 필수 컬럼 누락. 헤더: {raw_header}")
            return FALLBACK_PORTFOLIO

        ri_type   = raw_col["자산종류"]
        ri_ticker = raw_col[ticker_col]
        ri_name   = raw_col["종목명"]

        name_to_ticker: dict[str, tuple[str, str]] = {}  # {종목명: (ticker, market)}
        for row in raw_rows[1:]:
            if len(row) <= max(ri_type, ri_ticker, ri_name):
                continue
            if not _is_target(row[ri_type]):
                continue
            raw_ticker = row[ri_ticker].strip()
            name = row[ri_name].strip()
            if not raw_ticker or not name:
                continue
            # 이미 등록된 종목명은 첫 번째 행 우선
            if name not in name_to_ticker:
                ticker, market = _normalize_ticker(raw_ticker, row[ri_type])
                name_to_ticker[name] = (ticker, market)

        # ── 2단계: 종목별 현황 시트에서 비중·1d변동 읽기 ──
        summary_ws = spreadsheet.worksheet("종목별 현황")
        summary_rows = summary_ws.get_all_values()

        if not summary_rows:
            logger.warning("종목별 현황 시트가 비어 있습니다. 폴백 포트폴리오를 사용합니다.")
            return FALLBACK_PORTFOLIO

        # E열=index 4(비중), F열=index 5(변동 1d) — 헤더 행은 건너뜀
        IDX_ASSET_TYPE = 1
        IDX_NAME       = 2
        IDX_WEIGHT     = 4  # E열
        IDX_CHANGE_1D  = 5  # F열

        portfolio = []
        seen_names: set[str] = set()

        for row in summary_rows[1:]:
            if len(row) <= IDX_CHANGE_1D:
                continue
            asset_type = row[IDX_ASSET_TYPE].strip()
            if not _is_target(asset_type):
                continue

            name = row[IDX_NAME].strip()
            if not name or name in seen_names:
                continue
            seen_names.add(name)

            weight    = _parse_pct(row[IDX_WEIGHT])
            change_1d = _parse_pct(row[IDX_CHANGE_1D])

            if weight <= 0:
                continue

            if name not in name_to_ticker:
                logger.warning(f"'{name}'의 티커를 raw 시트에서 찾을 수 없습니다. 스킵합니다.")
                continue

            ticker, market = name_to_ticker[name]
            portfolio.append({
                "ticker":    ticker,
                "name":      name,
                "weight":    weight,
                "change_1d": change_1d,
                "market":    market,
            })

        if not portfolio:
            logger.warning("포트폴리오에서 유효한 종목을 찾지 못했습니다. 폴백 포트폴리오를 사용합니다.")
            return FALLBACK_PORTFOLIO

        # 비중 내림차순 정렬
        portfolio.sort(key=lambda x: x["weight"], reverse=True)
        logger.info(f"포트폴리오 로드 완료: {len(portfolio)}개 종목")
        return portfolio

    except Exception as e:
        logger.warning(f"포트폴리오 로드 실패: {e}. 폴백 포트폴리오를 사용합니다.")
        return FALLBACK_PORTFOLIO
