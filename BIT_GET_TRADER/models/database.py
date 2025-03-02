import sqlite3
from config import DB_PATH, NEWS_DB_PATH

def initialize_database():
    """데이터베이스와 필요한 테이블을 초기화합니다."""
    # 트레이딩 데이터베이스 초기화
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS ai_responses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                decision TEXT NOT NULL,
                reason TEXT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()
    
    # 뉴스 데이터베이스 초기화
    with sqlite3.connect(NEWS_DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS crypto_news (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                content TEXT,
                crypto_type TEXT NOT NULL,
                published_date DATETIME NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()

def save_ai_response(decision, reason):
    """AI의 응답을 데이터베이스에 저장합니다."""
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO ai_responses (decision, reason) VALUES (?, ?)
        """, (decision, reason))
        conn.commit()

def get_latest_ai_responses(limit=2):
    """저장된 AI 응답 중 최신 N개를 가져옵니다."""
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT decision, reason, timestamp
            FROM ai_responses
            ORDER BY timestamp DESC
            LIMIT ?
        """, (limit,))
        rows = cursor.fetchall()
    return [
        {"decision": row[0], "reason": row[1], "timestamp": row[2]}
        for row in rows
    ]

def get_latest_btc_news():
    """최신 암호화폐 뉴스를 가져옵니다."""
    with sqlite3.connect(NEWS_DB_PATH) as conn:
        cursor = conn.cursor()
        query = """
            SELECT title, published_date 
            FROM crypto_news 
            WHERE crypto_type = 'Bitcoin' 
            ORDER BY published_date DESC 
            LIMIT 3
        """
        cursor.execute(query)
        news = cursor.fetchall()
    return [{"title": item[0], "date": item[1]} for item in news] 