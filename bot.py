import os
import time
import random

# SIMULAÇÃO (não opera de verdade ainda)

saldo = 1000

def gerar_sinal():
    return random.choice(["COMPRA", "VENDA", None])

while True:
    sinal = gerar_sinal()

    if sinal:
        print(f"Sinal detectado: {sinal}")

    time.sleep(5)
