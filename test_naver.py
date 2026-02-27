import os
import urllib.request
import urllib.parse
import json
from dotenv import load_dotenv

load_dotenv()

client_id = os.getenv("NAVER_CLIENT_ID")
client_secret = os.getenv("NAVER_CLIENT_SECRET")

if not client_id or not client_secret:
    print("Naver API keys not found in .env")
else:
    encText = urllib.parse.quote("SK하이닉스")
    url = f"https://openapi.naver.com/v1/search/news?query={encText}&display=5&sort=sim"
    
    request = urllib.request.Request(url)
    request.add_header("X-Naver-Client-Id", client_id)
    request.add_header("X-Naver-Client-Secret", client_secret)
    
    try:
        response = urllib.request.urlopen(request)
        rescode = response.getcode()
        if rescode == 200:
            response_body = response.read()
            data = json.loads(response_body.decode('utf-8'))
            print(json.dumps(data, ensure_ascii=False, indent=2))
        else:
            print("Error Code:" + rescode)
    except Exception as e:
        print(f"Error: {e}")
