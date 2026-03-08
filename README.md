# AssetBrief

개인 투자자를 위한 맞춤형 자산 뉴스 브리핑 에이전트입니다.

Yahoo Finance, Tavily, 네이버 뉴스, Google News RSS, DART 공시 등 다양한 소스에서 뉴스를 수집하고, Google Gemini AI로 분석하여 **텔레그램으로 일일 브리핑**을 전송합니다.

---

## 주요 기능

- **포트폴리오 자동 연동**: 구글 시트에서 보유 종목·비중·1D 변동률을 실시간으로 읽어옴
- **다중 뉴스 소스**: Yahoo Finance, Tavily, 네이버 뉴스 API, Google News RSS, DART 공시
- **AI 분석 (Gemini)**:
  - 개별 종목 3줄 브리핑 (Gemini 2.5 Flash)
  - 핵심 트렌드 1줄 요약 추출
  - 글로벌 매크로 인사이트 (Gemini 2.5 Pro)
- **하이브리드 투자 관점**: 가치투자 70% + 모멘텀 트레이딩 30% 비중의 분석 필터
- **ETF 지원**: ETF 이름·브랜드를 자동 감지하고, 테마·섹터 기반 검색어를 AI로 생성
- **스마트 정렬**: `비중 × |1D 변동률|` 점수로 임팩트 큰 종목을 먼저 전송
- **오전/오후 세션**: KST 기준 오전에는 US→KR 순, 오후에는 KR→US 순으로 브리핑

---

## 설치

**Python 3.10 이상** 필요

```bash
git clone <repo-url>
cd asset-brief

python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate

pip install -r requirements.txt
```

---

## 환경 변수 설정

`.env` 파일을 루트에 생성하고 아래 키를 입력합니다.

```dotenv
# 필수
GOOGLE_API_KEY=your_gemini_api_key
TAVILY_API_KEY=your_tavily_api_key
TELEGRAM_BOT_TOKEN=your_telegram_bot_token
TELEGRAM_CHAT_ID=your_telegram_chat_id

# 구글 시트 포트폴리오 연동 (선택, 없으면 하드코딩 포트폴리오 사용)
GOOGLE_SHEET_ID=your_google_sheet_id
GOOGLE_SERVICE_ACCOUNT_FILE=../asset-treemap/service_account.json

# 네이버 뉴스 API (선택, 없으면 Google News RSS로 폴백)
NAVER_CLIENT_ID=your_naver_client_id
NAVER_SECRET_KEY=your_naver_secret_key

# DART 공시 (선택, 없으면 한국 공시 미수집)
DART_API_KEY=your_dart_api_key
```

### API 키 발급 안내

| 서비스 | 발급처 | 용도 |
|---|---|---|
| Google Gemini | [Google AI Studio](https://aistudio.google.com/) | 뉴스 분석·요약 |
| Tavily | [Tavily](https://tavily.com/) | 고품질 뉴스 검색 (검색당 1크레딧) |
| Telegram Bot | [@BotFather](https://t.me/BotFather) | 브리핑 메시지 수신 |
| 네이버 뉴스 API | [네이버 개발자센터](https://developers.naver.com/) | 국내 뉴스 검색 |
| DART | [DART Open API](https://opendart.fss.or.kr/) | 한국 기업 공시 |

---

## 포트폴리오 설정

### 구글 시트 연동 (권장)

구글 시트에 두 개의 탭이 필요합니다.

**① 종목별 현황(raw)** — 티커 매핑 탭

| 종목명 | 자산종류 | Ticker |
|---|---|---|
| SK하이닉스 | 국내주식 | 000660 |
| Apple | 해외주식 | AAPL |

- `자산종류` 컬럼이 `국내주식` 또는 `해외주식`인 행만 처리됨
- 6자리 숫자 티커는 자동으로 `.KS` 형식으로 변환 (예: `000660` → `000660.KS`)
- `BRK.B` 형태는 `BRK-B`로 자동 변환

**② 종목별 현황** — 비중·변동 탭

| (A) | (B) 자산종류 | (C) 종목명 | (D) | (E) 비중 | (F) 변동 1d |
|---|---|---|---|---|---|
| | 국내주식 | SK하이닉스 | | 15.3% | -2.1% |

E열에 비중(%), F열에 1D 변동(%)을 입력합니다.

### 하드코딩 폴백

구글 시트 연동 없이도 `services/portfolio.py`의 `FALLBACK_PORTFOLIO`에 직접 종목을 추가하면 바로 사용할 수 있습니다.

---

## 실행

```bash
# 전체 시장 (KST 기준 오전/오후 자동 감지)
python main.py

# 시장 선택
python main.py --market us   # 미국 시장만
python main.py --market kr   # 한국 시장만

# 세션 강제 지정
python main.py --session am   # 오전: US → KR 순
python main.py --session pm   # 오후: KR → US 순
```

---

## 브리핑 예시

```
📈 AssetBrief 데일리 브리핑 (전체)
2025-01-15

<b>[💡 오늘의 핵심 인사이트]</b>
미 연준의 금리 동결 기조가 유지되는 가운데...

━━━━━━━━━━━━━━━

<b>[📊 시장 지표]</b>
S&P 500  1D -0.3% | 1W +1.2% | 1M +3.5%
KOSPI    1D +0.5% | ...

━━━━━━━━━━
<b>SK하이닉스 (000660.KS)</b>
비중 15.3% · 임팩트 -0.3bp
현재가 145,000원 | 1D -2.1%

<b>AI 반도체 수요 폭발로 어닝 서프라이즈</b>

<b>[🌏 외신]</b>
- HBM 수요가 예상치를 30% 상회하며...

<b>[🇰🇷 국내]</b>
- 3분기 영업이익 컨센서스 상향 조정...
```

---

## 아키텍처

```
main.py (오케스트레이터)
├── services/portfolio.py   ← 구글 시트에서 포트폴리오 로드
├── services/news.py        ← 멀티소스 뉴스 수집 (Tavily / yfinance / Naver / RSS)
├── services/dart.py        ← 한국 기업 DART 공시
├── services/llm.py         ← Gemini AI 분석 (Flash / Pro)
├── services/notifier.py    ← 텔레그램 전송
├── utils/market.py         ← 시장 데이터, 티커 분류, ETF 판별
└── config/prompts.py       ← AI 시스템 프롬프트 (70/30 전략 인코딩)
```

**데이터 흐름**: 포트폴리오 로드 → 뉴스 수집 → 시장 데이터 조회 → AI 분석 → 비중×변동 정렬 → 텔레그램 전송

---

## 자동화 (크론)

매일 정해진 시각에 자동 실행하려면 `crontab -e`로 등록합니다.

```cron
# 오전 8시 (KST) — 해외 시장 마감 후
0 8 * * 1-5 cd /path/to/asset-brief && /path/to/venv/bin/python main.py --session am

# 오후 6시 (KST) — 국내 시장 마감 후
0 18 * * 1-5 cd /path/to/asset-brief && /path/to/venv/bin/python main.py --session pm
```
