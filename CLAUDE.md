# CLAUDE.md

이 파일은 Claude Code(claude.ai/code)가 이 저장소의 코드 작업 시 참고할 가이드를 제공합니다.

## 프로젝트 개요

AssetBrief는 개인 투자자를 위한 맞춤형 자산 뉴스 브리핑 에이전트입니다. 여러 소스(Yahoo Finance, Tavily, Naver News, Google News RSS, DART 공시)로부터 금융 뉴스를 수집하고, Google의 Gemini AI로 분석한 뒤 텔레그램을 통해 일일 브리핑을 전송합니다.

시스템은 하이브리드 투자 전략을 구현합니다: 70% 가치투자 + 30% 모멘텀 트레이딩, 이는 뉴스 필터링과 분석에 모두 반영됩니다.

## 개발 명령어

### 설정
```bash
# 의존성 설치
pip install -r requirements.txt

# .env 파일을 복사하고 API 키 설정 (환경 변수 섹션 참조)
```

### 애플리케이션 실행
```bash
# 모든 시장(US + KR) 실행
python main.py

# 미국 시장만 실행
python main.py --market us

# 한국 시장만 실행
python main.py --market kr
```

### 테스트
```bash
# 글로벌 시장 인사이트 생성 테스트
python test_global_insight.py

# 네이버 뉴스 API 통합 테스트
python test_naver.py

# 긴 메시지 청킹 로직 테스트
python test_chunk2.py
```

## 아키텍처

### 데이터 흐름
1. **뉴스 수집** (`services/news.py`): 여러 소스에서 뉴스 수집
   - 미국 주식: Yahoo Finance (yfinance) + Tavily 검색 (신뢰 도메인)
   - 한국 주식: Yahoo Finance + Tavily (영어로 된 글로벌 뉴스) + Naver News API / Google News RSS (한국 로컬 뉴스)
   - Tavily 결과가 없으면 Google News RSS로 폴백

2. **시장 데이터** (`utils/market.py`): yfinance를 통해 가격 및 복수 기간 변동률 데이터 조회
   - 개별 자산: 현재가 + 1D/1M 변동률
   - 글로벌 시장 지수 (S&P 500, Nasdaq, KOSPI 등) 복수 기간 변동률

3. **DART 공시** (`services/dart.py`): 한국 주식만 대상으로 최근 기업 공시 조회

4. **AI 분석** (`services/llm.py`):
   - 개별 자산 브리핑: Gemini 2.5 Flash (빠르고 저렴함)
   - 핵심 트렌드 추출: Gemini 2.5 Flash (초저온도 0.1)
   - 글로벌 시장 인사이트: Gemini 2.5 Pro 스트리밍 (타임아웃 시 Flash로 폴백)

5. **메시지 조립 및 전달** (`main.py`):
   - 글로벌 인사이트, 시장 현황, 개별 자산 브리프를 결합
   - 텔레그램 4096자 제한 초과 시 자동 분할
   - 텔레그램 Bot API를 통해 전송 (`services/notifier.py`)

### 주요 설계 패턴

**하이브리드 투자 전략 (70/30)**
- 뉴스 필터링과 프롬프트는 가치 중심 정보(실적, 경쟁 우위, 전략적 결정)를 70%, 모멘텀/감성 요소를 30%로 우선순위 부여
- `config/prompts.py`의 시스템 프롬프트에 7:3 비율이 명시적으로 인코딩됨

**계층적 폴백을 갖춘 다중 소스 뉴스**
- 1차: yfinance (무료, 큐레이션됨) + Tavily (검색당 1크레딧, 고품질)
- 2차: Naver News API (무료, 한국만) + Google News RSS (무료, 범용)
- Tavily는 신뢰 도메인 필터를 사용하여 노이즈 감소 (`services/news.py`의 `TRUSTED_DOMAINS_US`, `TRUSTED_DOMAINS_KR`)

**날짜 필터링 전략**
- Tavily 결과는 게시일 기준으로 엄격하게 필터링하여 최신성 보장
- API가 `published_date`를 제공하지 않을 경우 URL 기반 날짜 추출과 HTML 메타 태그 파싱으로 폴백
- Naver News API는 날짜순 정렬 (`sort=date`)하고 24시간 윈도우로 필터링
- 날짜를 알 수 없는 기사는 오래된 콘텐츠를 방지하기 위해 제외

**한국 주식 이중 언어 검색**
- 글로벌 뉴스: `KR_GLOBAL_QUERY_MAP`을 사용한 영어 쿼리 (회사명 + 산업 키워드)로 미국 도메인 대상
- 로컬 뉴스: 한국어 회사명으로 한국 도메인 대상 (또는 Naver/Google RSS)

**메시지 청킹**
- 텔레그램은 메시지당 4096자 제한
- 주요 콘텐츠를 논리적 청크로 분할 (글로벌 인사이트 → 시장 현황 → 개별 브리프)
- 각 청크는 제한을 준수하며, 진행 표시기와 함께 순차 전달

### 모듈별 역할

- `main.py`: 오케스트레이션, 인자 파싱, 메시지 조립, 청킹
- `services/news.py`: 소스별 로직을 갖춘 뉴스 집계 (Tavily, yfinance, Naver, Google RSS, DART)
- `services/llm.py`: Gemini 클라이언트 싱글톤, 스트리밍 지원 비동기 콘텐츠 생성
- `services/dart.py`: 한국 기업 공시를 위한 OpenDartReader 통합
- `services/notifier.py`: HTML 파싱 및 자동 링크 변환을 갖춘 텔레그램 메시지 전달
- `utils/market.py`: yfinance 데이터 조회, 티커 분류 (US vs KR), 한국 티커 이름 매핑
- `config/prompts.py`: 다양한 분석 컨텍스트를 위한 시스템 지시문 (US_STOCK, KR_STOCK, GLOBAL_INSIGHT, EXTRACT_TREND)

## 환경 변수

`.env`에 필요한 키:
- `GOOGLE_API_KEY`: Google Gemini API 키
- `TAVILY_API_KEY`: Tavily 검색 API 키 (뉴스 검색)
- `TELEGRAM_BOT_TOKEN`: 텔레그램 봇 토큰
- `TELEGRAM_CHAT_ID`: 메시지 전달 대상 채팅 ID
- `NAVER_CLIENT_ID`: Naver News API 클라이언트 ID (선택, 한국 뉴스용)
- `NAVER_SECRET_KEY`: Naver News API 시크릿 (선택, 한국 뉴스용)
- `DART_API_KEY`: DART (금융감독원) API 키 (선택, 한국 공시용)

앱은 서비스 임포트 전에 `main.py` 상단에서 `python-dotenv`를 통해 `.env`를 로드합니다.

## 주요 구현 사항

### 티커 처리
- 미국 티커: 일반 형식 (예: `AAPL`, `MSFT`)
- 한국 티커: yfinance 형식으로 `.KS` 또는 `.KQ` 접미사 (예: `000660.KS`)
- DART API는 6자리 코드만 필요 (`.KS`/`.KQ` 제거)
- 한국 티커-이름 매핑은 `utils/market.py::KR_TICKER_NAME_MAP`에 하드코딩됨

### 뉴스 소스 우선순위
**미국 주식**의 경우:
1. yfinance 뉴스 (무료, Yahoo Finance 큐레이션)
2. Tavily 검색 with `TRUSTED_DOMAINS_US` (1크레딧)
3. Google News RSS 폴백

**한국 주식**의 경우:
1. yfinance 뉴스 (글로벌 커버리지)
2. Tavily 검색 (영어 쿼리, 미국 도메인) - 글로벌 관점
3. Naver News API + Google News RSS (한국어 쿼리, 로컬 뉴스) → 둘 다 실패 시 Tavily로 폴백
4. DART 공시 (최근 2일)

### 에러 핸들링 및 타임아웃
- 개별 자산 실패는 전체 실행을 중단하지 않고 포착되고 로깅됨
- 글로벌 인사이트 생성은 45초 타임아웃; 타임아웃 시 Flash 모델로 폴백
- 뉴스 API 실패는 대체 소스로 폴백 (Google RSS 등)

### HTML 및 링크 처리
- 텔레그램 메시지는 HTML 파싱 모드 사용 (`<b>`, `<a href>`)
- `services/notifier.py::_auto_link_urls()`는 bare URL을 클릭 가능한 `<a>` 태그로 변환
- Naver News API는 제목/설명에 HTML 엔티티를 반환; BeautifulSoup으로 정제

### AI 모델 선택
- **Flash (gemini-2.5-flash)**: 개별 브리핑, 트렌드 추출 (빠르고 저렴함)
- **Pro (gemini-2.5-pro)**: 글로벌 시장 인사이트 (높은 품질, 스트리밍)
- Temperature: 0.1-0.3으로 환각 최소화 및 사실적 출력 보장
