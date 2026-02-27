import asyncio
import os
from dotenv import load_dotenv

load_dotenv()

async def test_run():
    from main import main
    import main as m
    m.KR_TICKERS = ["000660.KS"]
    await main(market="kr")
    
if __name__ == "__main__":
    asyncio.run(test_run())
