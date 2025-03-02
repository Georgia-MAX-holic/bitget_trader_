import os
from dotenv import load_dotenv

# 환경 변수 로드
load_dotenv()

# 거래 설정
TRADE_SIZES = 0.018
MODE = "4H_1D"
TRADING_TIMES = ["01:00", "05:00", "09:00", "13:00", "17:00", "21:00"]

# API 설정
BITGET_API_KEY = os.getenv("BITGET_API_KEY")
BITGET_API_SECRET = os.getenv("BITGET_API_SECRET")
BITGET_PASSPHRASE = os.getenv("BITGET_PASSPHRASE")
OPENAI_API_KEY = os.getenv("OPEN_API_KEY")

# 데이터베이스 설정
DB_PATH = 'trading_bot.db'
NEWS_DB_PATH = 'Crypto_news.db'

# 레버리지 설정
LEVERAGE = 20

# 손절매 설정
# STOP_LOSS_PERCENTAGE = 0.8  # 0.8%

# 환경 변수 및 전역 설정
TRADING_MODE = os.getenv("TRADING_MODE", "15m_30m").upper()

print(f"TRADING_MODE: {TRADING_MODE}")  # 디버깅용 출력