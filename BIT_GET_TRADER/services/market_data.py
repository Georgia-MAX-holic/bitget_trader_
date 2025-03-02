import requests
import pandas as pd
import ta
from pybitget.client import Client
from config import BITGET_API_KEY, BITGET_API_SECRET, BITGET_PASSPHRASE

def get_fear_and_greed_index():
    """공포 탐욕 지수를 가져옵니다."""
    url = "https://api.alternative.me/fng/"
    response = requests.get(url)
    if response.status_code == 200:
        return response.json().get('data', [{}])[0]
    else:
        print(f"Failed to fetch Fear and Greed Index. Status code: {response.status_code}")
        return None

def add_indicators(df, mode):
    """기술적 지표를 DataFrame에 추가합니다."""
    if 'close' not in df.columns:
        raise ValueError("Missing required 'close' column in DataFrame")

    df['close'] = pd.to_numeric(df['close'], errors='coerce')
    df = df.dropna()

    timeframes = {
        "1H_4H": (("1H", 20, 14, 26, 12, 9, 50, 20), ("4H", 40, 28, 52, 24, 18, 100, 40)),
        "15M_30M": (("15m", 20, 14, 26, 12, 9, 50, 20), ("30m", 40, 28, 52, 24, 18, 100, 40)),
        "1M_5M": (("1m", 20, 14, 26, 12, 9, 50, 20), ("5m", 40, 28, 52, 24, 18, 100, 40)),
        "4H_1D": (("4H", 20, 14, 26, 12, 9, 50, 20), ("1D", 40, 28, 52, 24, 18, 100, 40))
    }

    if mode not in timeframes:
        raise ValueError(f"Unsupported mode: {mode}")

    main_tf, aux_tf = timeframes[mode]

    for tf in [main_tf, aux_tf]:
        suffix = tf[0]
        bb = ta.volatility.BollingerBands(close=df['close'], window=tf[1], window_dev=2)
        df[f'bb_bbm_{suffix}'] = bb.bollinger_mavg()
        df[f'bb_bbh_{suffix}'] = bb.bollinger_hband()
        df[f'bb_bbl_{suffix}'] = bb.bollinger_lband()

        df[f'rsi_{suffix}'] = ta.momentum.RSIIndicator(close=df['close'], window=tf[2]).rsi()

        macd = ta.trend.MACD(close=df['close'], window_slow=tf[3], window_fast=tf[4], window_sign=tf[5])
        df[f'macd_{suffix}'] = macd.macd()
        df[f'macd_signal_{suffix}'] = macd.macd_signal()
        df[f'macd_diff_{suffix}'] = macd.macd_diff()

        df[f'sma_{tf[6]}_{suffix}'] = ta.trend.SMAIndicator(close=df['close'], window=tf[6]).sma_indicator()
        df[f'ema_{tf[7]}_{suffix}'] = ta.trend.EMAIndicator(close=df['close'], window=tf[7]).ema_indicator()

    return df

def fetch_candles(symbol, granularity, max_candles):
    """캔들 데이터를 가져오고 인디케이터를 추가한 DataFrame을 반환합니다."""
    client = Client(BITGET_API_KEY, BITGET_API_SECRET, BITGET_PASSPHRASE)
    
    # 서버 시간 가져오기 및 정수로 변환
    server_time_response = client.spot_get_server_time()
    current_time = int(server_time_response['data'])

    # 타임 범위 계산
    granularity_to_seconds = {
        "1M": 2592000, "1W": 604800, "1D": 86400,
        "4H": 14400, "1H": 3600, "30m": 1800,
        "15m": 900, "5m": 300, "3m": 180, "1m": 60
    }

    if granularity not in granularity_to_seconds:
        raise ValueError(f"Invalid granularity: {granularity}")

    time_interval = max_candles * granularity_to_seconds[granularity] * 1000
    start_time = current_time - time_interval

    # 캔들 데이터 가져오기
    candles = client.mix_get_candles(
        symbol=symbol,
        granularity=granularity,
        startTime=start_time,
        endTime=current_time
    )

    if not candles:
        raise ValueError("캔들 데이터가 반환되지 않았습니다.")

    df = pd.DataFrame(candles, columns=["timestamp", "open", "high", "low", "close", "volume", "extra"])
    df = df.drop(columns=["extra"], errors="ignore")
    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
    
    return df 