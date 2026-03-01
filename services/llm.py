import os
from google import genai
from google.genai import types
from utils.market import get_asset_type
from config.prompts import SYSTEM_PROMPTS

_client = None

def get_gemini_client():
    global _client
    if _client is None:
        google_api_key = os.getenv("GOOGLE_API_KEY")
        if google_api_key:
            _client = genai.Client(api_key=google_api_key)
    return _client

def summarize_news(ticker: str, name: str, news_data: str) -> str:
    """Gemini API를 이용해 뉴스를 투자자 관점에서 3줄 요약합니다."""
    gemini_client = get_gemini_client()
    if not gemini_client:
        return "⚠️ Google API 설정이 누락되어 뉴스를 요약할 수 없습니다."
        
    print(f"🧠 [{ticker}] Gemini가 뉴스를 분석 및 요약 중...\n")
    
    # 자산군에 따른 프롬프트 선택
    asset_type = get_asset_type(ticker)
    system_instruction = SYSTEM_PROMPTS.get(asset_type, SYSTEM_PROMPTS["US_STOCK"])
    
    if asset_type == "KR_STOCK":
        prompt = f"다음은 '{name}'({ticker})에 대한 오늘자 뉴스들이다. 외신과 국내 뉴스를 구분하여 각각 3줄씩 요약해줘. 요약 내용에 기업명이 들어갈 경우 가급적 '{name}'으로 표기해줘.\n{news_data}"
    else:
        prompt = f"다음은 '{name}'({ticker})에 대한 오늘자 뉴스들이다. 이를 분석해서 3줄로 브리핑해줘.\n{news_data}"
    
    # 모델 호출 (temperature를 낮춰서 할루시네이션을 줄이고 팩트 위주로 생성)
    try:
        response = gemini_client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt,
            config=types.GenerateContentConfig(
                system_instruction=system_instruction,
                temperature=0.2 
            )
        )
        return response.text
    except Exception as e:
        return f"⚠️ Gemini 생성 오류: {e}"

def generate_global_insight(market_status: str, market_news: str, ticker_briefs: str) -> str:
    """시장 지수, 시황 뉴스, 개별 종목 브리핑을 종합하여 인사이트를 도출합니다."""
    gemini_client = get_gemini_client()
    if not gemini_client:
        return ""

    model_name = 'gemini-3.1-pro-preview'
    print(f"🧠 전체 시장 인사이트 도출 중... ({model_name} 사용)\n")
    
    try:
        # 60초 타임아웃 설정하여 무한 대기 방지
        response = gemini_client.models.generate_content(
            model=model_name,
            contents=prompt,
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_PROMPTS.get("GLOBAL_INSIGHT", "당신은 투자 전문가입니다."),
                temperature=0.3,
                http_options={'timeout': 60}
            )
        )
        return response.text or "⚠️ 인사이트를 생성할 수 없습니다."
    except Exception as e:
        print(f"⚠️ Global Insight 생성 오류: {e}")
        # 타임아웃이나 오류 발생 시 Flash 모델로 재시도 (안정성 확보)
        try:
            print("🔄 Flash 모델로 재시도 중...")
            response = gemini_client.models.generate_content(
                model='gemini-2.0-flash',
                contents=prompt,
                config=types.GenerateContentConfig(
                    system_instruction=SYSTEM_PROMPTS.get("GLOBAL_INSIGHT", "당신은 투자 전문가입니다."),
                    temperature=0.2,
                    http_options={'timeout': 30}
                )
            )
            return response.text + "\n(⚠️ Pro 모델 지연으로 Flash 모델 결과가 제공되었습니다.)"
        except Exception as retry_e:
            return f"⚠️ 인사이트 생성 중 최종 오류가 발생했습니다: {retry_e}"
