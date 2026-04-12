import requests
import time
import pandas as pd

print("🚀 BOT COM ESTRATÉGIA INICIADO")

saldo = 1000
posicao = None
preco_entrada = 0


def pegar_candles():
    url = "https://api.mexc.com/api/v3/klines?symbol=BTCUSDT&interval=1h&limit=100"
    data = requests.get(url).json()

    df = pd.DataFrame(data, columns=[
        "time","open","high","low","close","volume",
        "close_time","qav","trades","tbav","tqav","ignore"
    ])

    df["close"] = df["close"].astype(float)
    df["high"] = df["high"].astype(float)
    df["low"] = df["low"].astype(float)
    df["volume"] = df["volume"].astype(float)

    return df


def calcular_indicadores(df):
    df["ema9"] = df["close"].ewm(span=9).mean()
    df["ema21"] = df["close"].ewm(span=21).mean()

    # RSI
    delta = df["close"].diff()
    gain = delta.clip(lower=0).rolling(14).mean()
    loss = -delta.clip(upper=0).rolling(14).mean()
    rs = gain / loss
    df["rsi"] = 100 - (100 / (1 + rs))

    # ROC
    df["roc"] = df["close"].pct_change(12)

    # WR
    high14 = df["high"].rolling(14).max()
    low14 = df["low"].rolling(14).min()
    df["wr"] = (high14 - df["close"]) / (high14 - low14) * -100

    # Volume médio
    df["vol_media"] = df["volume"].rolling(20).mean()

    # TRIX
    ema1 = df["close"].ewm(span=15).mean()
    ema2 = ema1.ewm(span=15).mean()
    ema3 = ema2.ewm(span=15).mean()
    df["trix"] = ema3.pct_change()

    return df


def gerar_sinal(df):
    last = df.iloc[-1]

    compra = (
        last["ema9"] > last["ema21"] and
        50 < last["rsi"] < 65 and
        last["roc"] > 0 and
        last["wr"] < -50 and
        last["volume"] > last["vol_media"] and
        last["trix"] > 0
    )

    venda = (
        last["ema9"] < last["ema21"] and
        35 < last["rsi"] < 50 and
        last["roc"] < 0 and
        last["wr"] > -50 and
        last["volume"] > last["vol_media"] and
        last["trix"] < 0
    )

    if compra:
        return "COMPRA"
    elif venda:
        return "VENDA"
    return None


while True:
    try:
        df = pegar_candles()
        df = calcular_indicadores(df)

        sinal = gerar_sinal(df)
        preco = df["close"].iloc[-1]

        print(f"💲 Preço: {preco}")

        if sinal and posicao is None:
            posicao = sinal
            preco_entrada = preco
            print(f"🚀 Entrada: {sinal} em {preco}")

        elif posicao == "COMPRA":
            lucro = preco - preco_entrada
            print(f"📊 Lucro: {lucro:.2f}")

            if abs(lucro) > 100:
                saldo += lucro
                print(f"💰 Fechou COMPRA | Saldo: {saldo:.2f}")
                posicao = None

        elif posicao == "VENDA":
            lucro = preco_entrada - preco
            print(f"📊 Lucro: {lucro:.2f}")

            if abs(lucro) > 100:
                saldo += lucro
                print(f"💰 Fechou VENDA | Saldo: {saldo:.2f}")
                posicao = None

        time.sleep(60)

    except Exception as e:
        print("Erro:", e)
        time.sleep(10)
