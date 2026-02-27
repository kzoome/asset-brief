import urllib.request
import feedparser
from datetime import datetime, timedelta
import ssl

def fetch_google_news(query: str, max_results: int = 5, days: int = 1):
    # RSS URL for Google News (Korean)
    # query encode
    import urllib.parse
    enc_query = urllib.parse.quote(query)
    url = f"https://news.google.com/rss/search?q={enc_query}&hl=ko&gl=KR&ceid=KR:ko"
    
    # Avoid SSL verification issues on some systems
    if hasattr(ssl, '_create_unverified_context'):
        ssl._create_default_https_context = ssl._create_unverified_context
        
    try:
        feed = feedparser.parse(url)
        cutoff = datetime.now() - timedelta(days=days)
        results = []
        
        for entry in feed.entries:
            pub_date_str = entry.get('published', '')
            if pub_date_str:
                # e.g., 'Fri, 27 Feb 2026 01:23:45 GMT'
                try:
                    # feedparser actually parses the date automatically
                    parsed_dt = datetime(*entry.published_parsed[:6])
                    if parsed_dt < cutoff:
                        continue # Skip old news
                except Exception as e:
                    print(f"Date error for {entry.title}: {e}")
                    pass
            
            results.append({
                "title": entry.title,
                "url": entry.link,
                "published": pub_date_str
            })
            if len(results) >= max_results:
                break
        return results
    except Exception as e:
        print(f"Failed to fetch RSS: {e}")
        return []

if __name__ == "__main__":
    news = fetch_google_news("SK하이닉스")
    for n in news:
        print(n)
