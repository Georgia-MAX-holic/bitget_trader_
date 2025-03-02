import logging
from pybitget.client import Client
from openai import OpenAI
import json
import logging
logging.basicConfig(level=logging.INFO)
import pandas as pd
from config import (
    BITGET_API_KEY, BITGET_API_SECRET, BITGET_PASSPHRASE,
    OPENAI_API_KEY, LEVERAGE
)
from models.database import save_ai_response, get_latest_btc_news, get_latest_ai_responses
from services.market_data import fetch_candles, get_fear_and_greed_index, add_indicators

def calculate_atr(df_main, period=14):
    """
    ATR(Average True Range)을 계산합니다.
    :param df_main: OHLCV 데이터프레임
    :param period: ATR 계산 기간 (기본값: 14)
    :return: ATR 값
    """
    high = df_main['high']
    low = df_main['low']
    close = df_main['close']
    
    # True Range 계산
    tr1 = abs(high - low)
    tr2 = abs(high - close.shift())
    tr3 = abs(low - close.shift())
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    
    # 초기 ATR은 SMA로 계산
    atr = tr.rolling(window=period, min_periods=period).mean()
    
    # 이후 ATR은 EMA로 계산
    atr.iloc[period:] = tr.ewm(span=period, adjust=False).mean().iloc[period:]
    
    return atr.iloc[-1]  # 최신 ATR 값 반환


class TradingService:
    def __init__(self, symbol, mode, use_trailing_stop=False):
        self.symbol = symbol
        self.mode = mode
        self.client = Client(BITGET_API_KEY, BITGET_API_SECRET, BITGET_PASSPHRASE)
        self.openai_client = OpenAI(api_key=OPENAI_API_KEY)
        self.current_position = None
        self.entry_price = None
        self.peak_price = None  # 트레일링 스탑용 고점
        self.trough_price = None  # 트레일링 스탑용 저점
        self.leverage = LEVERAGE  # 레버리지 20배
        self.trade_sizes = None  # trade_sizes 저장 변수 추가
        self.use_trailing_stop = use_trailing_stop  # 트레일링 스탑 사용 여부

    def _adjust_leverage(self):
        """레버리지를 설정합니다."""
        try:
            self.client.mix_adjust_leverage(
                symbol=self.symbol,
                marginCoin="USDT",
                leverage=self.leverage,
                holdSide="long"
            )
            self.client.mix_adjust_leverage(
                symbol=self.symbol,
                marginCoin="USDT",
                leverage=self.leverage,
                holdSide="short"
            )
        except Exception as e:
            logging.error(f"레버리지 조정 실패: {e}")

    def _get_market_data(self):
        """시장 데이터를 수집합니다."""
        if self.mode == "1H_4H":
            df_main = fetch_candles(self.symbol, "1H", 50)  # 1시간 봉 (메인)
            df_aux = fetch_candles(self.symbol, "4H", 50)  # 4시간 봉 (보조)
        elif self.mode == "15M_30M":
            df_main = fetch_candles(self.symbol, "15m", 100)  # 15분 봉 (메인)
            df_aux = fetch_candles(self.symbol, "30m", 80)  # 30분 봉 (보조)
        elif self.mode == "1M_5M":
            df_main = fetch_candles(self.symbol, "1m", 100)  # 1분 봉 (메인)
            df_aux = fetch_candles(self.symbol, "5m", 100)  # 5분 봉 (보조)
        elif self.mode == "4H_1D":
            df_main = fetch_candles(self.symbol, "4H", 100)  # 4시간 봉 (메인)
            df_aux = fetch_candles(self.symbol, "1D", 50)  # 1일 봉 (보조)
        else:
            raise ValueError(f"Unsupported mode: {self.mode}")

        df_main = add_indicators(df_main, self.mode)
        df_aux = add_indicators(df_aux, self.mode)

        return df_main, df_aux

    def _get_ai_decision(self, df_main, df_aux):
        """AI로부터 거래 결정을 받아옵니다."""
        try:
            account_info = self.client.mix_get_accounts(productType="umcbl")
            fear_greed_index = get_fear_and_greed_index()
            news_headlines = get_latest_btc_news()

            # 이전 AI 결정 조회
            previous_decisions = get_latest_ai_responses(limit=2)  # 최신 2개의 결정 조회
            previous_decisions_str = "\n".join(
                [f"Decision: {d['decision']}, Reason: {d['reason']}, Timestamp: {d['timestamp']}"
                 for d in previous_decisions]
            )

            df_main['timestamp'] = df_main['timestamp'].astype(str)
            df_aux['timestamp'] = df_aux['timestamp'].astype(str)

            response = self.openai_client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {
                        "role": "system",
                        "content": """
                            You are an expert in Bitcoin futures trading. Analyze the provided data, 
                            including technical indicators, market data, and the Fear and Greed Index. 
                            Select one of the Long Short options to trade.
                            Consider the previous decisions and reasons provided.
                            Response in JSON format.
                            Response Example:
                            {"decision": "open_long", "reason": "some technical, fundamental, and sentiment-based reason"}
                            {"decision": "open_short", "reason": "some technical, fundamental, and sentiment-based reason"}
                        """
                    },
                    {
                        "role": "user",
                        "content": json.dumps({
                            "investment_status": account_info,
                            "ohlcv_main": df_main.to_dict(orient='records'),
                            "ohlcv_aux": df_aux.to_dict(orient='records'),
                            "fear_greed_index": fear_greed_index,
                            "news": news_headlines,
                            "previous_decisions": previous_decisions_str
                        })
                    }
                ],
                response_format={"type": "json_object"},
                timeout=30
            )

            result = json.loads(response.choices[0].message.content)
            decision = result.get("decision")
            reason = result.get("reason", "No reason provided")

            if decision:
                save_ai_response(decision, reason)  # AI 결정 저장
                logging.info(f"AI Decision: {decision.upper()}")
                logging.info(f"Reason: {reason}")
                return decision
            
        except Exception as e:
            logging.error(f"AI 결정 실패: {e}")
            return None

    def _check_stop_conditions(self, latest_price):
        """ATR 기반 동적 손절/익절 조건을 확인합니다."""
        if not self.current_position or not self.entry_price:
            return False, False

        # ATR 및 전략 파라미터
        atr_multiplier = 1.5  # ATR 배수 (1.5~2 권장)
        risk_reward_ratio = 2  # 위험/보상 비율 (1:2 이상)
        asset_type = "crypto"  # crypto/stock/forex 설정

        # 자산 유형별 파라미터 동적 조정
        if asset_type == "crypto":
            atr_multiplier = 2.0
            min_stop = 0.02  # 최소 2% (레버리지 없을 때)
        elif asset_type == "stock":
            atr_multiplier = 1.2
            min_stop = 0.01  # 최소 1% (레버리지 없을 때)

        # 레버리지 반영: 손절폭과 최소 손절폭을 레버리지로 나눔
        min_stop = min_stop / self.leverage
        atr_multiplier = atr_multiplier / self.leverage

        # ATR 값 가져오기 (분봉 20기간 기준)
        df_main, _ = self._get_market_data()
        atr_value = calculate_atr(df_main, period=20)  # ATR 계산 함수 호출

        # 동적 손절가 계산 (ATR과 최소값 중 큰 값 사용)
        stop_loss_pct = max(atr_value * atr_multiplier, min_stop)
        take_profit_pct = stop_loss_pct * risk_reward_ratio

        # 포지션별 조건 체크
        if self.current_position == "long":
            stop_price = self.entry_price * (1 - stop_loss_pct)
            take_profit = self.entry_price * (1 + take_profit_pct)
            
            # 트레일링 스탑 적용시 (고점 대비 ATR 조정)
            if self.use_trailing_stop:
                self.peak_price = max(self.peak_price, latest_price)
                stop_price = self.peak_price * (1 - stop_loss_pct / 2)  # 절반 수준으로 강화
            
        elif self.current_position == "short":
            stop_price = self.entry_price * (1 + stop_loss_pct)
            take_profit = self.entry_price * (1 - take_profit_pct)
            
            if self.use_trailing_stop:
                self.trough_price = min(self.trough_price, latest_price)
                stop_price = self.trough_price * (1 + stop_loss_pct / 2)

        logging.info(f"Stop Price: {stop_price}, Take Profit: {take_profit}")
        logging.info(f"Stop Triggered: {stop_triggered}, Profit Triggered: {profit_triggered}")
        # 조건 충족 여부
        stop_triggered = (latest_price <= stop_price) if self.current_position == "long" else (latest_price >= stop_price)
        profit_triggered = (latest_price >= take_profit) if self.current_position == "long" else (latest_price <= take_profit)

        return stop_triggered, profit_triggered

    def execute_trade(self, trade_sizes=None):
        """거래를 실행합니다."""
        try:
            if trade_sizes is not None:
                self.trade_sizes = trade_sizes
                
            df_main, df_aux = self._get_market_data()
            latest_price = float(df_main['close'].iloc[-1])

            # 손절/익절 체크
            stop_triggered, profit_triggered = self._check_stop_conditions(latest_price)
            if stop_triggered or profit_triggered:
                if self.trade_sizes:
                    self._close_position(self.trade_sizes)
                return

            # AI 결정 받기
            decision = self._get_ai_decision(df_main, df_aux)

            # 레버리지 조정
            self._adjust_leverage()

            # 거래 실행
            if decision == "open_long":
                if self.current_position == "short":
                    self._close_position(self.trade_sizes)
                self._open_position("long", self.trade_sizes)
            elif decision == "open_short":
                if self.current_position == "long":
                    self._close_position(self.trade_sizes)
                self._open_position("short", self.trade_sizes)
            elif decision == "hold":
                self._close_position(self.trade_sizes)

        except Exception as e:
            logging.error(f"거래 실행 실패: {e}")

    def _close_position(self, trade_size):
        """현재 포지션을 종료합니다."""
        try:
            if self.current_position == "long":
                self.client.mix_place_order(
                    symbol=self.symbol,
                    side="close_long",
                    marginCoin="USDT",
                    size=trade_size,
                    orderType="market"
                )
                logging.info("롱 포지션 종료")
            elif self.current_position == "short":
                self.client.mix_place_order(
                    symbol=self.symbol,
                    side="close_short",
                    marginCoin="USDT",
                    size=trade_size,
                    orderType="market"
                )
                logging.info("숏 포지션 종료")
            
            self.current_position = None
            self.entry_price = None
        except Exception as e:
            logging.error(f"포지션 종료 실패: {e}")

    def _open_position(self, position_type, trade_size):
        """새로운 포지션을 엽니다."""
        try:
            side = "open_long" if position_type == "long" else "open_short"
            self.client.mix_place_order(
                symbol=self.symbol,
                side=side,
                marginCoin="USDT",
                size=trade_size,
                orderType="market"
            )
            self.current_position = position_type
            self.entry_price = float(self._get_market_data()[0]['close'].iloc[-1])
            logging.info(f"{position_type.capitalize()} 포지션 열기")
        except Exception as e:
            logging.error(f"포지션 열기 실패: {e}")