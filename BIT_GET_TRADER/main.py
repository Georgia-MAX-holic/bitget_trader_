import logging
import schedule
from functools import partial
from config import TRADE_SIZES, MODE, TRADING_TIMES
from models.database import initialize_database
from services.trading import TradingService
from services.news_service import NewsService

def setup_logging():
    """로깅 설정을 초기화합니다."""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler('trading.log'),
            logging.StreamHandler()
        ]
    )

def main():
    """메인 실행 함수"""
    # 로깅 설정
    setup_logging()
    logging.info("트레이딩 봇 시작")

    # 데이터베이스 초기화
    initialize_database()

    # 서비스 초기화
    trading_service = TradingService("BTCUSDT_UMCBL", MODE)
    news_service = NewsService()

    # 뉴스 수집 첫 실행 및 스케줄링
    logging.info("뉴스 수집 시작")
    news_service.fetch_crypto_news()
    schedule.every(60).minutes.do(news_service.fetch_crypto_news)  # 30분마다 뉴스 수집

    # 트레이딩 서비스 초기화
    if MODE == "1H_4H":
        schedule_interval = 60  # 1시간마다
        schedule.every(schedule_interval).minutes.do(
            partial(trading_service.execute_trade, TRADE_SIZES)
        )
    elif MODE == "15M_30M":
        schedule_interval = 15  # 15분마다
        schedule.every(schedule_interval).minutes.do(
            partial(trading_service.execute_trade, TRADE_SIZES)
        )
    elif MODE == "1M_5M":
        schedule_interval = 1  # 1분마다
        schedule.every(schedule_interval).minutes.do(
            partial(trading_service.execute_trade, TRADE_SIZES)
        )
    elif MODE == "4H_1D":
        # 지정된 시간에 실행
        for time in TRADING_TIMES:
            schedule.every().day.at(time).do(
                partial(trading_service.execute_trade, TRADE_SIZES)
            )
    else:
        raise ValueError(f"지원하지 않는 모드입니다: {MODE}")

    logging.info(f"트레이딩 봇이 {MODE} 모드로 시작되었습니다.")

    # 첫 실행
    trading_service.execute_trade(TRADE_SIZES)

    # 스케줄러 실행
    while True:
        try:
            schedule.run_pending()
        except Exception as e:
            logging.error(f"스케줄러 실행 중 오류 발생: {e}")

if __name__ == "__main__":
    main() 