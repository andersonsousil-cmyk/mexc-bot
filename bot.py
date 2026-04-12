print("BOT INICIADO")
import requests
import time
import random

saldo = 1000
posicao = None
preco_entrada = 0

def pegar_preco():
    url = "https://api.mexc.com/api/v3/ticker/price?symbol=BTCUSDT"
    response = requests.get(url)
    data = response.json()
    return float(data["price"])

def gerar_sinal():
    return random.choice(["COMPRA", "VENDA", None])

while True:
    preco = pegar_preco()
    sinal = gerar_sinal()

    print(f"Preço atual: {preco}")

    if sinal and posicao is None:
        posicao = sinal
        preco_entrada = preco
        print(f"🚀 Entrou em {sinal} a {preco}")

    elif posicao == "COMPRA":
        lucro = preco - preco_entrada
        print(f"📊 Lucro: {lucro:.2f}")

        if abs(lucro) > 50:
            saldo += lucro
            print(f"💰 Fechou COMPRA | Novo saldo: {saldo:.2f}")
            posicao = None

    elif posicao == "VENDA":
        lucro = preco_entrada - preco
        print(f"📊 Lucro: {lucro:.2f}")

        if abs(lucro) > 50:
            saldo += lucro
            print(f"💰 Fechou VENDA | Novo saldo: {saldo:.2f}")
            posicao = None

    time.sleep(5)
