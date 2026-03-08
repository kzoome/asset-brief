# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

이 파일은 Claude Code(claude.ai/code)가 이 저장소의 코드 작업 시 참고할 가이드를 제공합니다.

## 프로젝트 개요

AssetBrief는 개인 투자자를 위한 맞춤형 자산 뉴스 브리핑 에이전트입니다. 여러 소스(Yahoo Finance, Tavily, Naver News, Google News RSS, DART 공시)로부터 금융 뉴스를 수집하고, Google의 Gemini AI로 분석한 뒤 텔레그램을 통해 일일 브리핑을 전송합니다.

시스템은 하이브리드 투자 전략을 구현합니다: 70% 가치투자 + 30% 모멘텀 트레이딩, 이는 뉴스 필터링과 분석에 모두 반영됩니다.

## 개발 명령어

### 설정
```bash
# 의존성 설치 (venv 내)
venv/bin/pip install -r requirements.txt
```

> **중요**: `source venv/bin/activate`가 제대로 작동하지 않을 수 있으므로, Python 직접 경로를 사용한다.
> ```bash
> /Users/al02633347/workspace-p/asset-brief/venv/bin/python main.py
> ```

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

### 테스트 스크립트
```bash
python test_global_insight.py   # 글로벌 시장 인사이트 생성
python test_naver.py            # 네이버 뉴스 API 통합
python test_chunk2.py           # 텔레그램 메시지 청킹 로직
python list_models.py           # 사용 가능한 Gemini 모델 목록 조회
```

## 아키텍처

### 데이터 흐름
1. **포트폴리오 로드** (`services/portfolio.py`): 구글 시트 "종목별 현황(raw)" + "종목별 현황" 탭에서 비중·1D변동 읽기. 실패 시 `FALLBACK_PORTFOLIO` 사용.

2. **뉴스 수집** (`services/news.py`): 여러 소스에서 뉴스 수집
   - 미국 주식: yfinance + Tavily (신뢰 도메인 필터링)
   - 한국 주식: yfinance + Tavily (영어 쿼리, 글로벌 관점) + Naver News API / Google News RSS (한국어 쿼리)
   - ETF: `extract_etf_queries()`로 테마/섹터 키워드 동적 생성 후 검색

3. **시장 데이터** (`utils/market.py`): yfinance를 통해 가격 및 변동률 데이터 조회

4. **DART 공시** (`services/dart.py`): 한국 주식(비ETF)만 최근 2일 공시 조회

5. **AI 분석** (`services/llm.py`):
   - 개별 자산 브리핑: Gemini 2.5 Flash (temperature 0.2)
   - 핵심 트렌드 추출: Gemini 2.5 Flash (temperature 0.1)
   - ETF 검색 쿼리 생성: Gemini 2.5 Flash (JSON 형식 출력)
   - 글로벌 시장 인사이트: Gemini 2.5 Pro 스트리밍, 45초 타임아웃 시 Flash로 폴백

6. **정렬 및 메시지 조립** (`main.py`): `비중 × |1D 변동률|` 점수로 내림차순 정렬 → 텔레그램 4096자 제한 고려 청크 분할 전송

### 모듈별 역할

- `main.py`: 오케스트레이션, CLI 인수 파싱, 메시지 조립·청킹
- `services/portfolio.py`: 구글 시트 연동 및 FALLBACK_PORTFOLIO 정의
- `services/news.py`: 소스별 뉴스 집계 (Tavily, yfinance, Naver, Google RSS)
- `services/llm.py`: Gemini 클라이언트 싱글톤, 비동기 콘텐츠 생성
- `services/dart.py`: 한국 기업 공시 (OpenDartReader)
- `services/notifier.py`: 텔레그램 메시지 전달, bare URL → `<a>` 태그 변환
- `utils/market.py`: yfinance 데이터 조회, 티커 분류 (US/KR), ETF 판별, `KR_TICKER_NAME_MAP`
- `config/prompts.py`: 시스템 프롬프트 (US_STOCK, KR_STOCK, GLOBAL_INSIGHT, EXTRACT_TREND)

### 주요 설계 패턴

**포트폴리오 로드 (2단계 조인)**
- "종목별 현황(raw)" 탭: `종목명 → (ticker, market)` 매핑 구성
- "종목별 현황" 탭: 비중(E열) + 1D 변동(F열) 읽기 후 조인
- 6자리 숫자 티커 → `.KS` 자동 변환, `BRK.B` → `BRK-B` 변환

**ETF 처리**
- `is_etf(ticker, name)`: 이름에 "ETF", "FUND" 포함 또는 한국 ETF 브랜드 접두사(`TIGER`, `KODEX` 등)로 판별
- ETF는 DART 공시 미조회. `extract_etf_queries()`로 테마 기반 검색어 생성

**날짜 필터링**
- Tavily: 게시일 기준 엄격 필터, API 미제공 시 URL·HTML 메타 태그로 폴백
- Naver: `sort=date`, 24시간 윈도우 필터
- 날짜 불명 기사는 제외

**메시지 청킹**
- 4096자 제한 초과 시: 글로벌 인사이트 → 시장 지표 → 개별 브리프 순으로 논리적 청크 분할
- 각 개별 브리프는 청크 단위로 독립 유지

## 환경 변수

`.env`에 필요한 키:
- `GOOGLE_API_KEY`: Google Gemini API 키
- `TAVILY_API_KEY`: Tavily 검색 API 키
- `TELEGRAM_BOT_TOKEN`: 텔레그램 봇 토큰
- `TELEGRAM_CHAT_ID`: 메시지 전달 대상 채팅 ID
- `GOOGLE_SHEET_ID`: 구글 시트 ID (포트폴리오 연동)
- `GOOGLE_SERVICE_ACCOUNT_FILE`: 서비스 계정 JSON 경로 (기본값: `../asset-treemap/service_account.json`)
- `NAVER_CLIENT_ID` / `NAVER_SECRET_KEY`: Naver News API (선택)
- `DART_API_KEY`: DART 공시 API (선택)

## 주요 구현 사항

### 티커 처리
- 미국 티커: 일반 형식 (예: `AAPL`, `BRK-B`)
- 한국 티커: `.KS` 또는 `.KQ` 접미사 (예: `000660.KS`)
- DART API는 6자리 코드만 필요 (`.KS`/`.KQ` 제거)
- 한국 티커-이름 매핑: `utils/market.py::KR_TICKER_NAME_MAP` (하드코딩)
- 구글 시트에서 name이 제공되면 매핑보다 우선 사용

### 뉴스 소스 우선순위
**미국 주식**: yfinance → Tavily (`TRUSTED_DOMAINS_US`) → Google News RSS

**한국 주식**: yfinance → Tavily 영어 쿼리 (`KR_GLOBAL_QUERY_MAP`) → Naver News API + Google News RSS (둘 다 실패 시 Tavily 폴백) → DART 공시

### AI 모델
- **Flash (gemini-2.5-flash)**: 개별 브리핑, 트렌드 추출, ETF 쿼리 생성
- **Pro (gemini-2.5-pro)**: 글로벌 시장 인사이트 (스트리밍, 45초 타임아웃)
- Temperature: 0.1–0.3 (환각 최소화)

### HTML 및 링크
- 텔레그램: HTML 파싱 모드 (`<b>`, `<a href>`)
- `services/notifier.py::_auto_link_urls()`: bare URL → 클릭 가능한 링크
- Naver News API 응답의 HTML 엔티티는 BeautifulSoup으로 정제
