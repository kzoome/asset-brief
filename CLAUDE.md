# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

이 파일은 Claude Code(claude.ai/code)가 이 저장소의 코드 작업 시 참고할 가이드를 제공합니다.

## 프로젝트 개요

AssetBrief는 보유 종목 뉴스를 모아 텔레그램으로 보내 주는 일일 브리핑 봇입니다. 구글 시트에서 보유 종목·비중·1D 변동을 읽고, 여러 소스(Yahoo Finance, Tavily, Naver News, Google News RSS, DART 공시)에서 종목별 뉴스를 수집한 뒤, Gemini로 **종목당 핵심 사실 1문장**을 뽑아 시장 지표와 함께 전송합니다.

## 개발 명령어

### 설정
```bash
python -m venv venv
venv/bin/pip install -r requirements.txt
```

> **중요**: `source venv/bin/activate`가 제대로 작동하지 않을 수 있으므로, venv의 Python을 직접 경로로 호출한다.
> ```bash
> venv/bin/python main.py
> ```
> 로컬 맥에는 venv가 없을 수 있다. 실제 운영은 서버에서 돈다(아래 "배포·스케줄" 참고).

### 애플리케이션 실행
```bash
# 모든 시장(US + KR) 실행, KST 기준 오전/오후 자동 감지
python main.py

# 시장 선택
python main.py --market us   # 미국 시장만
python main.py --market kr   # 한국 시장만

# 세션 강제 지정 (오전=US→KR 순, 오후=KR→US 순)
python main.py --session am
python main.py --session pm
python main.py --market all --session auto   # 기본값
```

### 보조 스크립트
```bash
python test_naver.py            # 네이버 뉴스 API 호출 확인 (원본 JSON 출력)
python test_chunk2.py           # 메시지 청킹 알고리즘 단독 시뮬레이션 (main.py를 import하지 않음)
python list_models.py           # 사용 가능한 Gemini 모델 목록 조회
python test_global_insight.py   # ⚠️ 현재 동작 안 함 (아래 "미사용 코드" 참고)
```
자동화된 테스트 스위트는 없다.

## 아키텍처

### 데이터 흐름 (`main.py`)
1. **시장 지표** (`utils/market.py::get_global_market_status`): S&P 500(us/all), KOSPI(kr/all), USD/KRW(항상)의 현재값과 1D·1M 변동률.
2. **포트폴리오 로드** (`services/portfolio.py`): 구글 시트에서 종목·비중·1D 변동·주가 읽기. 실패 시 `FALLBACK_PORTFOLIO`.
3. **정렬**: 세션 기준 시장 그룹(오전=US 먼저, 오후=KR 먼저) → 그룹 안에서 `비중 × |1D 변동률|` 내림차순.
4. **종목별 처리** (종목마다 순차 실행):
   - ETF면 `extract_etf_queries()`로 테마 검색어 생성
   - `get_asset_news()`로 뉴스 수집
   - 국내 비ETF 종목은 DART 최근 2일 공시를 뉴스 뒤에 붙임
   - `summarize_news_short()`로 핵심 사실 1문장 생성
   - 종목 단위 예외는 잡아서 요약 없이 종목 줄만 출력
5. **메시지 조립·전송**: 헤더 + 시장 지표 + 종목 줄들을 4096자 기준으로 나눠 텔레그램 전송.

### 모듈별 역할

- `main.py`: 오케스트레이션, CLI 인수 파싱, 정렬, 메시지 포맷·청킹
- `services/portfolio.py`: 구글 시트 연동(2단계 조인) 및 `FALLBACK_PORTFOLIO` 정의
- `services/news.py`: 소스별 뉴스 집계 (yfinance, Tavily, Naver, Google RSS)
- `services/llm.py`: Gemini 클라이언트 싱글톤, 재시도·폴백, 단문 요약·ETF 검색어 생성
- `services/dart.py`: 한국 기업 공시 (OpenDartReader)
- `services/notifier.py`: 텔레그램 HTML 메시지 전송, bare URL → `<a>` 태그 변환
- `utils/market.py`: 시장 지표, 티커 분류(US/KR), ETF 판별, `KR_TICKER_NAME_MAP`
- `config/prompts.py`: 시스템 프롬프트. 실제로 쓰이는 것은 `US_STOCK_SHORT`, `KR_STOCK_SHORT`

### 주요 설계 패턴

**포트폴리오 로드 (2단계 조인)**
- "종목별 현황(raw)" 탭: 헤더 이름으로 컬럼을 찾는다. `종목명`·`자산종류`·`Ticker`(또는 `티커`)는 필수이고, `주가`·`Currency`는 선택이다(없으면 price=None). 이 탭으로 `종목명 → (ticker, market, price, currency)` 매핑을 만든다. 같은 종목명이 여러 행이면 첫 행을 쓴다.
- "종목별 현황" 탭: 고정 열 위치를 쓴다. B=자산종류, C=종목명, E=비중, F=1D 변동. raw 매핑과 종목명으로 조인한다.
- `자산종류`에 "국내주식"/"해외주식"이 포함된 행만 처리한다. market은 자산종류로 정한다(국내주식→kr, 그 외→us).
- 비중 0 이하 종목은 제외하고, raw 탭에 없는 종목명은 경고 후 건너뛴다.
- 6자리 숫자 티커 → `.KS` 변환(항상 `.KS`, `.KQ`는 붙이지 않음), `BRK.B` → `BRK-B` 변환
- 서비스 계정 기본 경로: 이 저장소 상위 폴더의 `asset-treemap/service_account.json`

**ETF 처리**
- `is_etf(ticker, name)`: 이름에 "ETF"/" FUND" 포함, 또는 첫 단어가 한국 ETF 브랜드(`TIGER`, `KODEX`, `ACE`, `SOL`, `PLUS` 등)이면 ETF로 본다.
- ETF는 DART 공시를 조회하지 않는다. `extract_etf_queries()`가 `{english_query, korean_query}`를 만들고, 실패하면 `"{ticker} ETF"`/종목명으로 폴백한다.
- 국내 ETF의 Tavily 외신 검색은 `min_score=0.35`로 엄격하게 거른다(일반 종목은 0.03).

**뉴스 소스 (`get_asset_news`)**
- 공통: yfinance 뉴스 (최근 2일, 제목 관련성 필터)
- 미국 주식: Tavily(`TRUSTED_DOMAINS_US`, `"{ticker} OR \"{회사명}\""` 쿼리)와 영어판 Google News RSS를 **항상 함께** 수집한다.
  - RSS 쿼리는 회사명이다(`Inc`·`Corp`·`Class B` 등 제거, 예: "Berkshire Hathaway"). 제목에 회사명이 들어간 기사만 남긴다. ETF는 ETF 검색어를 그대로 쓰고 제목 필터를 적용하지 않는다.
  - 도입 이유: Tavily는 관련도 점수 기준선(0.1)과 좁은 범위 때문에, 대형주에서도 관련 기사를 자주 놓쳤다(2026-11 BRK·MSFT가 "특이사항 없음"으로 나옴).
- 한국 주식:
  1. Tavily 외신. 쿼리는 `KR_GLOBAL_QUERY_MAP`(없으면 yfinance shortName), 대상은 `TRUSTED_DOMAINS_US`.
  2. Naver News API와 Google News RSS를 **둘 다** 수집한다(한국어 쿼리 = 종목명). 둘 다 비면 Tavily(`TRUSTED_DOMAINS_KR`)로 폴백.
  3. 비ETF는 `main.py`에서 DART 공시를 추가한다.
- Tavily는 basic 검색(1크레딧/건)이다. 종목당 미국 1회, 한국 1~2회.

**날짜 필터링**
- Tavily: `days=1`로 검색하고 결과를 2일 기준으로 다시 거른다. 게시일이 없으면 URL → HTML 메타 태그 순으로 추정하고, 그래도 모르면 신뢰 도메인 기사만 통과시킨다.
- Naver: `sort=date`로 100건을 받아 2일 안의 기사만 남기고, 24시간 이내 기사를 먼저 쓴다.
- Google News RSS: 2일 기준으로 거른다.

**LLM (`services/llm.py`)**
- 단문 요약 `summarize_news_short`: `gemini-3.5-flash-lite`, temperature 0.1, 자산군별 `*_SHORT` 프롬프트를 쓴다. 규칙은 "20자 내외 팩트 1문장, 가격 등락 자체는 쓰지 말고 원인만, 기사 Date 기준 최근 소식 우선, 없으면 '특이사항 없음'"이다. 실패하면 `gemini-3.1-flash-lite`로 폴백한다.
  - 입력에 오늘 날짜(KST)와 시트의 실제 1D 등락률(참고용)을 함께 넣는다. 지난 기사 속 등락을 오늘 일처럼 쓰지 않게 하려는 것이다.
  - `get_asset_news`는 기사마다 발행일(`Date:`)을 붙인다. 발행일을 모르는 기사는 생략한다.
- ETF 검색어 `extract_etf_queries`: `gemini-3.5-flash-lite`, temperature 0.1, JSON 응답 파싱
- 모델 선택 이유: API 키가 무료 등급(Default Gemini Project)이다. 무료 등급에서 Flash 계열(2.5/3.x)은 하루 20회라 한 번 돌 때 종목 수만큼 호출하는 브리프에 모자란다. 그래서 하루 500회인 Flash-Lite 두 모델(3.5, 3.1)을 쓴다. 한도는 모델마다 따로 센다.
- `_generate_with_retry`: 429/500/503에 지수 백오프(5→10→20→40s, 최대 5회)

**메시지 포맷·청킹**
- 헤더: `📈 AssetBrief 데일리 브리핑 ({전체|🇺🇸 해외 주식|🇰🇷 국내 주식})` + 날짜
- 이어서 `[📊 시장 지표]` 블록, `[🔍 오늘의 브리핑]` 블록, 그리고 종목 줄이 온다. 종목 줄 형식은 `📈/📉/➖ <b>종목명</b>  현재가 / 비중 x% / ±y%`이고, 다음 줄에 요약 1문장이 붙는다.
- 파트(시장 지표, 브리핑 제목, 종목 줄 각각)를 이어 붙이다가 4096자를 넘으면 새 메시지로 나눈다. 종목 줄은 쪼개지지 않는다.
- 텔레그램 HTML 파싱 모드(`<b>`, `<a href>`). `_auto_link_urls()`는 bare URL을 도메인명 링크로 바꾸고, 링크만 있는 연속 줄은 한 줄로 합친다.

### 미사용 코드 (레거시)
브리핑 포맷을 간소화하면서(`4f57317`, `761105c`) 아래 코드는 `main.py`에서 더 이상 호출되지 않는다. 지우지 않고 남아 있다.
- `services/llm.py`: `summarize_news`(3줄 브리핑), `extract_core_trend`, `generate_global_insight`(Gemini 2.5 Pro)
- `services/news.py`: `get_market_news`
- `utils/market.py`: `get_market_data`, `get_upcoming_events`, `get_1d_change_pct`
- `config/prompts.py`: `US_STOCK`, `KR_STOCK`, `GLOBAL_INSIGHT`, `EXTRACT_TREND`
- `config/rss_urls.json`: 어디서도 읽지 않음
- `test_global_insight.py`: `generate_global_insight(status, news)`로 인자 2개를 넘기는데, 함수는 인자 1개만 받아서 실행하면 실패한다.

## 배포·스케줄
- `master`에 푸시하면 `.github/workflows/deploy.yml`이 SSH로 서버(`/home/rocky/asset-brief`)에 접속해 `git reset --hard origin/master`와 `pip install`을 실행한다.
- 실행 스케줄은 저장소에 없고 서버 crontab에서 관리한다. GitHub Actions 스케줄 워크플로는 `e528777`에서 제거했다.
- 서버 Python 호환성 때문에 타입 힌트(`X | None`)를 쓰는 모듈은 `from __future__ import annotations`가 필요하다(Python 3.9 대응).

## 환경 변수

`.env`에 필요한 키:
- `GOOGLE_API_KEY`: Google Gemini API 키 (없으면 요약 없이 종목 줄만 전송)
- `TAVILY_API_KEY`: Tavily 검색 API 키
- `TELEGRAM_BOT_TOKEN`: 텔레그램 봇 토큰
- `TELEGRAM_CHAT_ID`: 메시지 전달 대상 채팅 ID
- `GOOGLE_SHEET_ID`: 구글 시트 ID (없으면 폴백 포트폴리오)
- `GOOGLE_SERVICE_ACCOUNT_FILE`: 서비스 계정 JSON 경로 (기본값: 저장소 상위 폴더의 `asset-treemap/service_account.json`)
- `NAVER_CLIENT_ID` / `NAVER_SECRET_KEY`: Naver News API (선택)
- `DART_API_KEY`: DART 공시 API (선택)

## 티커 처리
- 미국 티커: 일반 형식 (예: `AAPL`, `BRK-B`)
- 한국 티커: `.KS` 또는 `.KQ` 접미사 (예: `000660.KS`). 시트에서 오는 티커는 항상 `.KS`다.
- DART는 6자리 코드를 쓴다. 우선주는 끝자리를 `0`으로 바꿔 보통주 기업코드로 조회한다.
- 종목명은 시트 값을 우선 쓰고, 없으면 `KR_TICKER_NAME_MAP`, 그다음 yfinance shortName을 쓴다.
- Naver News API 응답의 HTML 엔티티는 BeautifulSoup으로 정제한다.
