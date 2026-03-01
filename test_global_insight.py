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
    trend_ledger = "[Apple] AI 아이폰 기대감으로 상승 반전\n[Samsung] HBM3E 양산 본격화로 수익성 개선 전망"
    insight = generate_global_insight(status, news, trend_ledger)
    print("--- [Generated Insight] ---")
    print(insight)
    print(f"DEBUG: insight length: {len(insight)}")
    assert len(insight) > 0
    print("✅ Global Insight OK\n")

if __name__ == "__main__":
    asyncio.run(test())
