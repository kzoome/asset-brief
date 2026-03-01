import re
header = "📈 헤더입니다\n\n"
global_insight = "전체 시장 인사이트입니다. " * 300 # 매우 긴 인사이트 생성 (약 4000자 이상 의도)
market_status = "시장 지표입니다.\n" * 50
all_briefs = [f"종목 {i} 어쩌구 저쩌구\n"*50 for i in range(15)]

MAX_LEN = 1000 # 테스트용으로 작게 설정 (비율상)

chunks = []
current = header

all_parts = []
if global_insight:
    all_parts.append(global_insight + "\n\n" + "━" * 15 + "\n")
if market_status:
    all_parts.append(f"<b>[📊 시장 지표]</b>\n{market_status}\n\n")
for brief in all_briefs:
    all_parts.append(brief + "\n\n")

for part in all_parts:
    if len(current) + len(part) > MAX_LEN:
        if current.strip():
            chunks.append(current.rstrip())
        current = part
    else:
        current += part

if current.strip():
    chunks.append(current.rstrip())

for i, chunk in enumerate(chunks, 1):
    print(f"--- Part {i} ---")
    print(f"길이: {len(chunk)}")
    print(chunk[:100] + "...(생략)...\n")
