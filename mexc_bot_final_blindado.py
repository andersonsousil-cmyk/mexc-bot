"""
BOT TELEGRAM MEXC - MONITORAMENTO AUTOMATICO DE SINAIS
Versao Blindada V3: Texto Bruto Total (Sem formatacao) + Sensibilidade Ajustada
"""

import asyncio
import json
import time
import requests
import pandas as pd
import numpy as np
from datetime import datetime
from typing import Dict, List, Tuple
import websockets
from telegram import Bot
from telegram.error import TelegramError, RetryAfter, TimedOut
from telegram.request import HTTPXRequest

# =============================================
# CONFIGURACAO - SEUS DADOS
# =============================================
TELEGRAM_TOKEN = "8754816911:AAGWSEssIpihNLwrVCLlpZFokBWsfnpP24M"
TELEGRAM_CHAT_ID = "-1003913555187"

API_KEY = "mx0vgLpfdtcQHJwqf"
API_SECRET = "bab18b5c57d44b7c993fb046b4c8c29"

# =============================================
# CONFIGURACAO - 30 CRIPTOMOEDAS
# =============================================
MOEDAS_PARA_MONITORAR = [
    "BTC_USDT", "ETH_USDT", "BNB_USDT", "XRP_USDT", "SOL_USDT",
    "ADA_USDT", "DOGE_USDT", "AVAX_USDT", "DOT_USDT", "LINK_USDT",
    "MATIC_USDT", "UNI_USDT", "ATOM_USDT", "LTC_USDT", "ETC_USDT",
    "FIL_USDT", "APT_USDT", "ARB_USDT", "OP_USDT", "SUI_USDT",
    "NEAR_USDT", "ALGO_USDT", "VET_USDT", "ICP_USDT", "GRT_USDT",
    "SAND_USDT", "MANA_USDT", "AXS_USDT", "EGLD_USDT", "THETA_USDT"
]

# AJUSTES PARA TESTE E MERCADO ATUAL (MAIS SENSIVEIS)
TIMEFRAME = "Min15"        # Reduzido para 15 minutos para sinais mais rapidos
INTERVALO_MIN_ALERTAS = 10 # Reduzido para 10 minutos
CONFIANCA_MINIMA = 50      # Reduzido para 50% (menos restritivo)
ADX_MINIMO = 15            # Reduzido para 15 (tendencias mais leves)
# =============================================

class MexcMonitorBot:

    def __init__(self):
        self.symbols = [s.upper() for s in MOEDAS_PARA_MONITORAR]
        self.ws_url = "wss://contract.mexc.com/edge"
        self.price_cache: Dict[str, pd.DataFrame] = {}
        self.last_alert: Dict[str, Dict[str, float]] = {}
        
        # Configurar bot com timeout maior para evitar erros de rede
        t_request = HTTPXRequest(connect_timeout=20, read_timeout=20)
        self.telegram = Bot(token=TELEGRAM_TOKEN, request=t_request)

        print("🤖 Inicializando Bot MEXC Blindado V3...")
        self._carregar_dados_historicos()

    def _carregar_dados_historicos(self):
        url = "https://contract.mexc.com/api/v1/contract/kline/{}"
        for symbol in self.symbols:
            try:
                endpoint_url = url.format(symbol)
                params = {"interval": TIMEFRAME}
                response = requests.get(endpoint_url, params=params, timeout=15)
                data = response.json()
                if data.get("success") and "data" in data and data["data"]:
                    kline_data = data["data"]
                    df = pd.DataFrame({
                        "timestamp": kline_data.get("time", []),
                        "open": kline_data.get("open", []),
                        "high": kline_data.get("high", []),
                        "low": kline_data.get("low", []),
                        "close": kline_data.get("close", []),
                        "volume": kline_data.get("vol", [])
                    })
                    for col in ["open", "high", "low", "close", "volume"]:
                        df[col] = df[col].astype(float)
                    df["timestamp"] = pd.to_datetime(df["timestamp"], unit="s")
                    if len(df) > 100: df = df.iloc[-100:].reset_index(drop=True)
                    self.price_cache[symbol] = df
                    print(f"✅ {symbol}: {len(df)} velas carregadas")
                else:
                    self.price_cache[symbol] = pd.DataFrame(columns=["timestamp", "open", "high", "low", "close", "volume"])
            except Exception as e:
                print(f"❌ {symbol}: Erro - {e}")
                self.price_cache[symbol] = pd.DataFrame(columns=["timestamp", "open", "high", "low", "close", "volume"])
            time.sleep(0.2)

    def _calcular_indicadores(self, df: pd.DataFrame) -> Dict:
        if df.empty or len(df) < 30: return {}
        close, high, low = df["close"], df["high"], df["low"]
        
        # ATR
        tr1 = high - low
        tr2 = abs(high - close.shift(1))
        tr3 = abs(low - close.shift(1))
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        atr = tr.rolling(window=14).mean()

        # ADX
        plus_dm = high.diff()
        minus_dm = low.diff()
        plus_dm[plus_dm < 0] = 0
        minus_dm[minus_dm > 0] = 0
        minus_dm = abs(minus_dm)
        tr_smooth = tr.rolling(window=14).mean()
        plus_di = 100 * (plus_dm.rolling(window=14).mean() / tr_smooth)
        minus_di = 100 * (minus_dm.rolling(window=14).mean() / tr_smooth)
        dx = 100 * abs(plus_di - minus_di) / (plus_di + minus_di)
        adx = dx.rolling(window=14).mean()

        # RSI
        delta = close.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))

        # SAR
        sar = pd.Series(index=high.index, dtype=float)
        trend, ep, af = 1, low.iloc[0], 0.02
        sar.iloc[0] = high.iloc[0]
        for i in range(1, len(high)):
            sar_i = sar.iloc[i-1] + af * (ep - sar.iloc[i-1])
            if trend == 1:
                if low.iloc[i] < sar_i: trend, sar_i, ep, af = -1, ep, high.iloc[i], 0.02
                elif high.iloc[i] > ep: ep, af = high.iloc[i], min(af + 0.02, 0.2)
            else:
                if high.iloc[i] > sar_i: trend, sar_i, ep, af = 1, ep, low.iloc[i], 0.02
                elif low.iloc[i] < ep: ep, af = low.iloc[i], min(af + 0.02, 0.2)
            sar.iloc[i] = sar_i

        last = -1
        return {
            "rsi": rsi.iloc[last] if not pd.isna(rsi.iloc[last]) else 50,
            "adx": adx.iloc[last] if not pd.isna(adx.iloc[last]) else 0,
            "atr": atr.iloc[last] if not pd.isna(atr.iloc[last]) else 0,
            "sar": sar.iloc[last] if not pd.isna(sar.iloc[last]) else close.iloc[last],
            "price": close.iloc[last]
        }

    def _analisar_sinal(self, ind: Dict) -> Tuple:
        if not ind or ind["adx"] < ADX_MINIMO: return None, 0, 0, 0, 0
        buy_pts, sell_pts = 0, 0
        if ind["price"] > ind["sar"]: buy_pts += 2
        else: sell_pts += 2
        if ind["rsi"] < 45: buy_pts += 1
        elif ind["rsi"] > 55: sell_pts += 1
        total = buy_pts + sell_pts
        if total == 0: return None, 0, 0, 0, 0
        price, atr = ind["price"], ind["atr"]
        if buy_pts > sell_pts:
            confianca = (buy_pts / total) * 100
            if confianca >= CONFIANCA_MINIMA:
                return "COMPRA", confianca, price, price + (atr * 2), price - (atr * 1.5)
        elif sell_pts > buy_pts:
            confianca = (sell_pts / total) * 100
            if confianca >= CONFIANCA_MINIMA:
                return "VENDA", confianca, price, price - (atr * 2), price + (atr * 1.5)
        return None, 0, 0, 0, 0

    async def _enviar_alerta(self, symbol: str, sinal: str, price: float, confianca: float, tp: float, sl: float, ind: Dict):
        agora = time.time()
        if symbol not in self.last_alert: self.last_alert[symbol] = {}
        ultimo = self.last_alert[symbol].get(sinal, 0)
        if agora - ultimo < INTERVALO_MIN_ALERTAS * 60: return
        self.last_alert[symbol][sinal] = agora
        
        # MENSAGEM EM TEXTO BRUTO TOTAL (SEM QUALQUER FORMATACAO)
        # Removidos emojis complexos e simbolos especiais para evitar erros de parsing
        msg = f"SINAL DE {sinal} - {symbol}\n"
        msg += f"Data: {datetime.now().strftime("%d/%m/%Y %H:%M")}\n\n"
        msg += f"ENTRADA: {price:.4f}\n"
        msg += f"TAKE PROFIT: {tp:.4f}\n"
        msg += f"STOP LOSS: {sl:.4f}\n\n"
        msg += f"Confianca: {confianca:.1f}%\n"
        msg += f"ADX: {ind["adx"]:.1f} | RSI: {ind["rsi"]:.1f}\n"
        msg += f"Timeframe: {TIMEFRAME}\n\n"
        msg += "Filtro de mercado lateral ativo."
        
        max_retries = 3
        for attempt in range(max_retries):
            try:
                # FORCANDO O ENVIO SEM QUALQUER PARSE_MODE
                await self.telegram.send_message(chat_id=TELEGRAM_CHAT_ID, text=msg, parse_mode=None)
                print(f"📤 Alerta enviado: {symbol} - {sinal}")
                break
            except RetryAfter as e:
                print(f"⚠️ Flood Control: Aguardando {e.retry_after} segundos...")
                await asyncio.sleep(e.retry_after)
            except (TimedOut, TelegramError) as e:
                if attempt < max_retries - 1:
                    print(f"⚠️ Erro Telegram ({e}): Tentativa {attempt+1}/{max_retries}. Aguardando 5s...")
                    await asyncio.sleep(5)
                else:
                    print(f"❌ Erro final ao enviar alerta: {e}")

    def _atualizar_cache(self, symbol: str, novo_preco: float):
        if symbol not in self.price_cache: return
        df = self.price_cache[symbol]
        if df.empty: return
        agora = pd.Timestamp.now()
        ultimo_tempo = df["timestamp"].iloc[-1]
        intervalo = {"Min1": 1, "Min5": 5, "Min15": 15, "Min30": 30, "Min60": 60, "H4": 240, "D1": 1440}.get(TIMEFRAME, 60)
        if (agora - ultimo_tempo).total_seconds() >= intervalo * 60:
            nova_linha = pd.DataFrame([{"timestamp": agora, "open": novo_preco, "high": novo_preco, "low": novo_preco, "close": novo_preco, "volume": 0}])
            df = pd.concat([df, nova_linha], ignore_index=True)
            if len(df) > 100: df = df.iloc[-100:].reset_index(drop=True)
        else:
            idx = df.index[-1]
            df.loc[idx, "close"] = novo_preco
            df.loc[idx, "high"] = max(df.loc[idx, "high"], novo_preco)
            df.loc[idx, "low"] = min(df.loc[idx, "low"], novo_preco)
        self.price_cache[symbol] = df
        ind = self._calcular_indicadores(df)
        if ind:
            sinal, conf, p, tp, sl = self._analisar_sinal(ind)
            if sinal: asyncio.create_task(self._enviar_alerta(symbol, sinal, p, conf, tp, sl, ind))

    async def _conectar_websocket(self):
        print(f"\n🔄 Conectando ao WebSocket...")
        while True:
            try:
                async with websockets.connect(
                    self.ws_url,
                    ping_interval=15,
                    ping_timeout=10,
                    close_timeout=5
                ) as ws:
                    print("✅ Conectado!")
                    for symbol in self.symbols:
                        await ws.send(json.dumps({"method": "sub.deal", "param": {"symbol": symbol}}))
                        await asyncio.sleep(0.1)
                    while True:
                        try:
                            msg = await asyncio.wait_for(ws.recv(), timeout=30)
                            data = json.loads(msg)
                            if data.get("channel") == "push.deal":
                                symbol = data.get("symbol")
                                trades = data.get("data", [])
                                if symbol in self.symbols and trades:
                                    price = float(trades[-1].get("p", 0))
                                    if price > 0: self._atualizar_cache(symbol, price)
                        except asyncio.TimeoutError:
                            await ws.send(json.dumps({"method": "ping"}))
            except Exception as e:
                if "1005" not in str(e):
                    print(f"⚠️ Erro WebSocket: {e}. Reconectando em 5s...")
                else:
                    print("🔄 Reconexao automatica do WebSocket (MEXC 1005)...")
                await asyncio.sleep(5)

    async def iniciar(self):
        await self._conectar_websocket()

if __name__ == "__main__":
    asyncio.run(MexcMonitorBot().iniciar())
