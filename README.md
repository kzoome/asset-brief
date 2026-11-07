# AssetBrief

보유 종목 뉴스를 모아 **텔레그램으로 일일 브리핑**을 보내 주는 봇입니다.

구글 시트에서 보유 종목·비중·1D 변동을 읽고, Yahoo Finance, Tavily, 네이버 뉴스, Google News RSS, DART 공시에서 종목별 뉴스를 수집한 뒤, Google Gemini로 종목마다 핵심 사실 1문장을 뽑아 시장 지표와 함께 전송합니다.

---

## 주요 기능

- **포트폴리오 자동 연동**: 구글 시트에서 보유 종목·비중·1D 변동률·현재가를 읽어옴
- **시장 지표**: S&P 500, KOSPI, USD/KRW의 현재값과 1D·1M 변동률
- **다중 뉴스 소스**: Yahoo Finance, Tavily, 네이버 뉴스 API, Google News RSS, DART 공시
- **종목별 한 줄 요약 (Gemini 3.5 Flash-Lite)**: 뉴스에서 주가·기업가치에 가장 유의미한 사실 1문장(20자 내외)을 추출. 뉴스가 없으면 "특이사항 없음"
- **ETF 지원**: ETF 이름·브랜드를 자동 감지하고, 담고 있는 테마·섹터 기반 검색어를 AI로 생성
- **오전/오후 세션**: KST 기준 오전에는 US→KR, 오후에는 KR→US 순으로 묶고, 각 그룹 안에서 `비중 × |1D 변동률|`이 큰 종목부터 표시

---

## 설치

**Python 3.9 이상** 필요

```bash
git clone <repo-url>
cd asset-brief

python -m venv venv
venv/bin/pip install -r requirements.txt
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

# 네이버 뉴스 API (선택, 없으면 Google News RSS만 사용)
NAVER_CLIENT_ID=your_naver_client_id
NAVER_SECRET_KEY=your_naver_secret_key

# DART 공시 (선택, 없으면 한국 공시 미수집)
DART_API_KEY=your_dart_api_key
```

`GOOGLE_SERVICE_ACCOUNT_FILE`을 비워 두면 저장소 상위 폴더의 `asset-treemap/service_account.json`을 사용합니다.

### API 키 발급 안내

| 서비스 | 발급처 | 용도 |
|---|---|---|
| Google Gemini | [Google AI Studio](https://aistudio.google.com/) | 뉴스 요약, ETF 검색어 생성 |
| Tavily | [Tavily](https://tavily.com/) | 뉴스 검색 (basic 검색 1크레딧/건, 종목당 미국 1회·한국 1~2회) |
| Telegram Bot | [@BotFather](https://t.me/BotFather) | 브리핑 메시지 수신 |
| 네이버 뉴스 API | [네이버 개발자센터](https://developers.naver.com/) | 국내 뉴스 검색 |
| DART | [DART Open API](https://opendart.fss.or.kr/) | 한국 기업 공시 |

---

## 포트폴리오 설정

### 구글 시트 연동 (권장)

구글 시트에 두 개의 탭이 필요합니다.

**① 종목별 현황(raw)** — 티커·주가 매핑 탭 (헤더 이름으로 컬럼을 찾음)

| 종목명 | 자산종류 | Ticker | 주가 | Currency |
|---|---|---|---|---|
| SK하이닉스 | 국내주식 | 000660 | 1,277,000 | KRW |
| Apple | 해외주식 | AAPL | 344.98 | USD |

- `종목명`·`자산종류`·`Ticker`(또는 `티커`)는 필수, `주가`·`Currency`는 선택(없으면 현재가 미표시)
- `자산종류`에 `국내주식` 또는 `해외주식`이 포함된 행만 처리
- 6자리 숫자 티커는 `.KS` 형식으로 변환 (예: `000660` → `000660.KS`)
- `BRK.B` 형태는 `BRK-B`로 변환

**② 종목별 현황** — 비중·변동 탭 (고정 열 위치)

| (A) | (B) 자산종류 | (C) 종목명 | (D) | (E) 비중 | (F) 변동 1d |
|---|---|---|---|---|---|
| | 국내주식 | SK하이닉스 | | 15.3% | -2.1% |

- E열 비중이 0 이하인 종목은 제외
- C열 종목명이 ① 탭에 없으면 건너뜀

### 하드코딩 폴백

시트 ID·서비스 계정이 없거나 로드에 실패하면 `services/portfolio.py`의 `FALLBACK_PORTFOLIO`를 사용합니다(비중·변동은 0으로 표시).

---

## 실행

```bash
# 전체 시장 (KST 기준 오전/오후 자동 감지)
venv/bin/python main.py

# 시장 선택
venv/bin/python main.py --market us   # 미국 시장만
venv/bin/python main.py --market kr   # 한국 시장만

# 세션 강제 지정
venv/bin/python main.py --session am   # 오전: US → KR 순
venv/bin/python main.py --session pm   # 오후: KR → US 순
```

---

## 브리핑 예시

```
📈 AssetBrief 데일리 브리핑 (전체)
2026-11-07

[📊 시장 지표]
• S&P 500: 6,850.12
  ╰─ 1D +0.4% / 1M +2.1%
• KOSPI: 4,012.55
  ╰─ 1D -0.8% / 1M +5.3%
• USD/KRW: 1,402.3
  ╰─ 1D +0.1% / 1M -0.6%

[🔍 오늘의 브리핑]

📈 Alphabet  $312.40 / 비중 8.2% / +1.9%
클라우드 매출 성장률 예상치 상회

📉 SK하이닉스  ₩1,277,000 / 비중 15.3% / -2.1%
HBM 공급 계약 단가 협상 지연 보도
```

텔레그램 4096자 제한을 넘으면 종목 줄 단위로 나눠 여러 메시지로 보냅니다.

---

## 아키텍처

```
main.py (오케스트레이터: 정렬·메시지 조립·청킹)
├── services/portfolio.py   ← 구글 시트에서 포트폴리오 로드
├── services/news.py        ← 멀티소스 뉴스 수집 (yfinance / Tavily / Naver / Google RSS)
├── services/dart.py        ← 한국 기업 DART 공시
├── services/llm.py         ← Gemini 단문 요약·ETF 검색어 생성 (재시도·폴백)
├── services/notifier.py    ← 텔레그램 전송
├── utils/market.py         ← 시장 지표, 티커 분류, ETF 판별
└── config/prompts.py       ← AI 시스템 프롬프트
```

**데이터 흐름**: 시장 지표 → 포트폴리오 로드 → 세션·점수 정렬 → 종목별 뉴스 수집(+DART) → Gemini 한 줄 요약 → 텔레그램 전송

---

## 배포·자동화

- `master` 브랜치에 푸시하면 GitHub Actions(`.github/workflows/deploy.yml`)가 SSH로 서버에 접속해 최신 코드를 받고 의존성을 설치합니다.
- 실행 스케줄은 서버의 crontab으로 관리합니다(저장소에는 없음). 예:

```cron
# 오전 8시 (KST) — 해외 시장 마감 후
0 8 * * 1-5 cd /path/to/asset-brief && venv/bin/python main.py --session am

# 오후 6시 (KST) — 국내 시장 마감 후
0 18 * * 1-5 cd /path/to/asset-brief && venv/bin/python main.py --session pm
```
