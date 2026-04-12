import os
import time
import hmac
import hashlib
import requests
import pandas as pd

# ================= CONFIG =================
API_KEY = os.getenv("mx0vglWNrSu1aY9PBN")
API_SECRET = os.getenv("04486ffae7984671b73e705c811b8e71")

SYMBOL = "BTC_USDT"
INTERVAL = "Min60"

LEVERAGE = 10
VALOR_TRADE = 5  # USDT por trade

STOP_LOSS_PERC = 0.02   # 2%
TAKE_PROFIT_PERC = 0.04 # 4%

SIMULACAO = False

BASE_URL = "https://contract.mexc.com"

em_posicao = False
preco_entrada = 0
tipo_posicao = None

# ================= AUTH =================
def gerar_assinatura(params):
    query = "&".join([f"{k}={params[k]}" for k in sorted(params)])
    return hmac.new(API_SECRET.encode(), query.encode(), hashlib.sha256).hexdigest()

# ================= API =================
def setar_leverage():
    endpoint = "/api/v1/private/position/change_leverage"
    params = {
        "symbol": SYMBOL,
        "leverage": LEVERAGE,
        "timestamp": int(time.time() * 1000)
    }
    params["sign"] = gerar_assinatura(params)
    headers = {"ApiKey": API_KEY}
    requests.post(BASE_URL + endpoint, params=params, headers=headers)

def executar_ordem(side):
    global em_posicao, preco_entrada, tipo_posicao

    if SIMULACAO:
        print(f"[SIMULAÇÃO] {side}")
        return

    endpoint = "/api/v1/private/order/submit"

    params = {
        "symbol": SYMBOL,
        "price": 0,
        "vol": VALOR_TRADE,
        "side": 1 if side == "BUY" else 2,
        "type": 1,
        "openType": 1,
        "leverage": LEVERAGE,
        "timestamp": int(time.time() * 1000)
    }

    params["sign"] = gerar_assinatura(params)
    headers = {"ApiKey": API_KEY}

    r = requests.post(BASE_URL + endpoint, params=params, headers=headers)
    print("ORDEM:", r.text)

    em_posicao = True
    tipo_posicao = side

def fechar_posicao():
    global em_posicao

    print("Fechando posição...")

    side = "SELL" if tipo_posicao == "BUY" else "BUY"
    executar_ordem(side)

    em_posicao = False

# ================= DADOS =================
def get_klines():
    url = f"{BASE_URL}/api/v1/contract/kline/{SYMBOL}?interval={INTERVAL}&limit=100"
    data = requests.get(url).json()["data"]

    df = pd.DataFrame(data).astype(float)
    return df

# ================= INDICADORES =================
def indicadores(df):
    close = df["close"]

    ema9 = close.ewm(span=9).mean()
    ema21 = close.ewm(span=21).mean()

    delta = close.diff()
    gain = delta.clip(lower=0).rolling(14).mean()
    loss = -delta.clip(upper=0).rolling(14).mean()
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))

    roc = close.pct_change(12)

    ema1 = close.ewm(span=15).mean()
    ema2 = ema1.ewm(span=15).mean()
    ema3 = ema2.ewm(span=15).mean()
    trix = ema3.pct_change()

    vol_media = df["vol"].rolling(20).mean()

    return {
        "price": close.iloc[-1],
        "ema9": ema9.iloc[-1],
        "ema21": ema21.iloc[-1],
        "rsi": rsi.iloc[-1],
        "roc": roc.iloc[-1],
        "trix": trix.iloc[-1],
        "volume": df["vol"].iloc[-1],
        "vol_media": vol_media.iloc[-1]
    }

# ================= ESTRATÉGIA =================
def analisar(ind):
    score_buy = 0
    score_sell = 0

    if ind["ema9"] > ind["ema21"]:
        score_buy += 2
    else:
        score_sell += 2

    if 45 < ind["rsi"] < 65:
        score_buy += 1
    elif 35 < ind["rsi"] < 55:
        score_sell += 1

    if ind["roc"] > 0:
        score_buy += 1
    else:
        score_sell += 1

    if ind["trix"] > 0:
        score_buy += 1
    else:
        score_sell += 1

    if ind["volume"] > ind["vol_media"]:
        score_buy += 1
        score_sell += 1

    total = score_buy + score_sell
    if total == 0:
        return None

    confianca = (max(score_buy, score_sell) / total) * 100

    if confianca < 60:
        return None

    return "BUY" if score_buy > score_sell else "SELL"

# ================= GERENCIAMENTO =================
def gerenciar_posicao(preco_atual):
    global em_posicao, preco_entrada, tipo_posicao

    if not em_posicao:
        return

    if tipo_posicao == "BUY":
        if preco_atual <= preco_entrada * (1 - STOP_LOSS_PERC):
            print("STOP LOSS acionado")
            fechar_posicao()

        elif preco_atual >= preco_entrada * (1 + TAKE_PROFIT_PERC):
            print("TAKE PROFIT acionado")
            fechar_posicao()

    elif tipo_posicao == "SELL":
        if preco_atual >= preco_entrada * (1 + STOP_LOSS_PERC):
            print("STOP LOSS acionado")
            fechar_posicao()

        elif preco_atual <= preco_entrada * (1 - TAKE_PROFIT_PERC):
            print("TAKE PROFIT acionado")
            fechar_posicao()

# ================= LOOP =================
def run():
    global preco_entrada

    print("🚀 BOT PROFISSIONAL RODANDO")

    setar_leverage()

    while True:
        try:
            df = get_klines()
            ind = indicadores(df)

            preco = ind["price"]
            sinal = analisar(ind)

            print(f"Preço: {preco} | RSI: {ind['rsi']:.2f}")

            if not em_posicao and sinal:
                print("ENTRADA:", sinal)
                executar_ordem(sinal)
                preco_entrada = preco

            gerenciar_posicao(preco)

            time.sleep(60)

        except Exception as e:
            print("ERRO:", e)
            time.sleep(10)

if __name__ == "__main__":
    run()
