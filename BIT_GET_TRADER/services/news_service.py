import requests
import sqlite3
from datetime import datetime
from bs4 import BeautifulSoup
from config import NEWS_DB_PATH

class NewsService:
    def __init__(self):
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }

    def fetch_crypto_news(self):
        """암호화폐 뉴스를 수집하고 데이터베이스에 저장합니다."""
        try:
            # 여러 뉴스 소스에서 데이터 수집
            self._fetch_from_coindesk()
            return True
        except Exception as e:
            print(f"뉴스 수집 중 오류 발생: {e}")
            return False

    def _fetch_from_coindesk(self):
        """CoinDesk Korea에서 뉴스를 수집합니다."""
        url = "https://www.coindeskkorea.com/news/articleList.html?sc_section_code=S1N1&view_type=sm"
        response = requests.get(url, headers=self.headers)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        news_items = soup.select('.article-list .list-block')
        
        with sqlite3.connect(NEWS_DB_PATH) as conn:
            cursor = conn.cursor()
            
            for item in news_items:
                try:
                    title = item.select_one('.list-titles').text.strip()
                    # 간단한 규칙으로 암호화폐 타입 결정
                    crypto_type = 'Bitcoin' if 'bitcoin' in title.lower() or '비트코인' in title else 'Other'
                    
                    # 현재 시간을 published_date로 사용
                    published_date = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    
                    # 중복 체크
                    cursor.execute("""
                        SELECT id FROM crypto_news 
                        WHERE title = ? AND published_date = ?
                    """, (title, published_date))
                    
                    if not cursor.fetchone():
                        cursor.execute("""
                            INSERT INTO crypto_news (title, crypto_type, published_date)
                            VALUES (?, ?, ?)
                        """, (title, crypto_type, published_date))
                
                except Exception as e:
                    print(f"뉴스 항목 처리 중 오류 발생: {e}")
                    continue
            
            conn.commit() 