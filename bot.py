import requests
import time
import random

print("🚀 BOT INICIADO")

saldo = 1000
posicao = None
preco_entrada = 0


def pegar_preco():
    try:
        url = "https://api.mexc.com/api/v3/ticker/price?symbol=BTCUSDT"
        response = requests.get(url, timeout=5)
        data = response.json()

        if "price" in data:
            return float(data["price"])
        else:
            print("❌ Erro ao pegar preço:", data)
            return None

    except Exception as e:
        print("❌ Erro API:", e)
        return None


def gerar_sinal():
    return random.choice(["COMPRA", "VENDA", None])


while True:
    try:
        preco = pegar_preco()

        if preco is None:
            time.sleep(5)
            continue

        print(f"💲 Preço atual: {preco}")

        sinal = gerar_sinal()

        # ENTRADA
        if sinal and posicao is None:
            posicao = sinal
            preco_entrada = preco
            print(f"🚀 Entrou em {sinal} a {preco}")

        # COMPRA
        elif posicao == "COMPRA":
            lucro = preco - preco_entrada
            print(f"📊 Lucro COMPRA: {lucro:.2f}")

            if abs(lucro) > 50:
                saldo += lucro
                print(f"💰 Fechou COMPRA | Saldo: {saldo:.2f}")
                posicao = None

        # VENDA
        elif posicao == "VENDA":
            lucro = preco_entrada - preco
            print(f"📊 Lucro VENDA: {lucro:.2f}")

            if abs(lucro) > 50:
                saldo += lucro
                print(f"💰 Fechou VENDA | Saldo: {saldo:.2f}")
                posicao = None

        time.sleep(5)

    except Exception as e:
        print("🔥 ERRO GERAL:", e)
        time.sleep(5)
