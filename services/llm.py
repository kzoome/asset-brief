import os
from google import genai
from google.genai import types
from utils.market import get_asset_type
from config.prompts import SYSTEM_PROMPTS

# main.py에서 load_dotenv()가 선행된 이후 로드되므로 정상 작동
google_api_key = os.getenv("GOOGLE_API_KEY")
gemini_client = genai.Client(api_key=google_api_key) if google_api_key else None

def summarize_news(ticker: str, news_data: str) -> str:
    """Gemini API를 이용해 뉴스를 투자자 관점에서 3줄 요약합니다."""
    if not gemini_client:
        return "⚠️ Google API 설정이 누락되어 뉴스를 요약할 수 없습니다."
        
    print(f"🧠 [{ticker}] Gemini가 뉴스를 분석 및 요약 중...\n")
    
    # 자산군에 따른 프롬프트 선택
    asset_type = get_asset_type(ticker)
    system_instruction = SYSTEM_PROMPTS.get(asset_type, SYSTEM_PROMPTS["US_STOCK"])
    
    if asset_type == "KR_STOCK":
        prompt = f"다음은 '{ticker}'에 대한 오늘자 뉴스들이다. 외신과 국내 뉴스를 구분하여 각각 3줄씩 요약해줘.\n{news_data}"
    else:
        prompt = f"다음은 '{ticker}'에 대한 오늘자 뉴스들이다. 이를 분석해서 3줄로 브리핑해줘.\n{news_data}"
    
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
