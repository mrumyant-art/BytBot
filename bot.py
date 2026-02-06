import os, time, asyncio, requests, datetime
import pandas as pd
import pandas_ta as ta
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
RR = 2.0 

def get_signals():
    # 1. Fetch Data
    url = "https://api.binance.com/api/v3/klines?symbol=BTCUSDT&interval=1m&limit=150"
    data = requests.get(url).json()
    df = pd.DataFrame(data, columns=['ts','o','h','l','c','v','ct','qv','nt','tb','tq','i'])
    c = df['c'].astype(float)
    
    # 2. Indicators
    ema200 = ta.ema(c, length=200)
    rsi = ta.rsi(c, length=14)
    macd = ta.macd(c)
    curr_p = c.iloc[-1]
    
    # 3. Calculation
    sl_dist = curr_p * 0.004
    tp_dist = sl_dist * RR

    # 4. Triple-Check Logic
    long = (curr_p > ema200.iloc[-1]) and (macd['MACDh_12_26_9'].iloc[-1] > 0) and (50 < rsi.iloc[-1] < 65)
    short = (curr_p < ema200.iloc[-1]) and (macd['MACDh_12_26_9'].iloc[-1] < 0) and (35 < rsi.iloc[-1] < 50)

    if long: return "🟢 LONG", curr_p, curr_p - sl_dist, curr_p + tp_dist
    if short: return "🔴 SHORT", curr_p, curr_p + sl_dist, curr_p - tp_dist
    return None, curr_p, 0, 0

async def scanner(context: ContextTypes.DEFAULT_TYPE):
    signal, price, sl, tp = get_signals()
    now = datetime.datetime.now()
    if 30 <= now.minute <= 50 and signal:
        msg = (f"🚨 *TRADE ALERT: {signal}*\n"
               f"💰 Entry: `${price:,.2f}`\n"
               f"🛑 SL: `${sl:,.2f}`\n"
               f"🎯 TP: `${tp:,.2f}`\n"
               f"⚖️ Ratio: `1:{int(RR)}`")
        await context.bot.send_message(CHAT_ID, msg, parse_mode='Markdown')

if __name__ == '__main__':
    app = ApplicationBuilder().token(TOKEN).build()
    app.job_queue.run_repeating(scanner, interval=60)
    app.run_polling(drop_pending_updates=True)
