import os
import asyncio
from dotenv import load_dotenv

# Load dotenv BEFORE importing services that depend on environment variables
load_dotenv()

from utils.market import get_global_market_status
from services.news import get_market_news
from services.llm import generate_global_insight

async def test():
    print("--- 1. Market Status Test ---")
    status = get_global_market_status("all")
    print(status)
    assert "S&P 500" in status
    assert "1Y:" in status
    assert "USD/KRW" in status
    print("✅ Market Status OK\n")

    print("--- 2. Market News Test ---")
    news = get_market_news("all")
    print(news[:500] + "...")
    assert len(news) > 0
    print("✅ Market News OK\n")

    print("--- 3. Global Insight Test ---")
    ticker_briefs = "- Apple: Q3 earnings beat expectations. (Source: reuters.com)\n- Samsung: HBM3E production ramp-up. (Source: hankyung.com)"
    insight = generate_global_insight(status, news, ticker_briefs)
    print("--- [Generated Insight] ---")
    print(insight)
    print(f"DEBUG: insight length: {len(insight)}")
    assert len(insight) > 0
    print("✅ Global Insight OK\n")

if __name__ == "__main__":
    asyncio.run(test())
