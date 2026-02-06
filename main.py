import os, time, asyncio, requests, datetime
import pandas as pd
import pandas_ta as ta
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

# --- CONFIGURATION ---
TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
RR_RATIO = 2.0  # 1:2 Risk-Reward
START_TIME = time.time()

def get_confirmed_signals():
    """Fetches data and performs the Triple-Check Analysis."""
    url = "https://api.binance.com/api/v3/klines?symbol=BTCUSDT&interval=1m&limit=150"
    try:
        data = requests.get(url, timeout=10).json()
        if not data or isinstance(data, dict): return None, 0, 0, 0, 0
        
        df = pd.DataFrame(data, columns=['ts','o','h','l','c','v','ct','qv','nt','tb','tq','i'])
        df['c'] = df['c'].astype(float)
        
        # 1. Calculate Indicators
        ema200 = ta.ema(df['c'], length=200)
        rsi = ta.rsi(df['c'], length=14)
        macd = ta.macd(df['c'])
        
        if df.empty or ema200 is None: return None, 0, 0, 0, 0
        
        curr_p = df['c'].iloc[-1]
        curr_rsi = rsi.iloc[-1]
        curr_macd_h = macd['MACDh_12_26_9'].iloc[-1]
        curr_ema200 = ema200.iloc[-1]

        # 2. Risk Management (0.4% SL buffer)
        sl_dist = curr_p * 0.004
        tp_dist = sl_dist * RR_RATIO

        # 3. Triple-Check Logic
        is_long = (curr_p > curr_ema200) and (curr_macd_h > 0) and (50 < curr_rsi < 65)
        is_short = (curr_p < curr_ema200) and (curr_macd_h < 0) and (35 < curr_rsi < 50)

        if is_long:
            return "🟢 LONG", curr_p, curr_p - sl_dist, curr_p + tp_dist, curr_rsi
        if is_short:
            return "🔴 SHORT", curr_p, curr_p + sl_dist, curr_p - tp_dist, curr_rsi
            
    except Exception as e:
        print(f"Data Fetch Error: {e}")
    return None, 0, 0, 0, 0

async def scanner_job(context: ContextTypes.DEFAULT_TYPE):
    signal, price, sl, tp, rsi = get_confirmed_signals()
    now = datetime.datetime.now()
    
    # Golden Window Alert (30-50 mins past the hour)
    if 30 <= now.minute <= 50 and signal:
        msg = (
            f"⚡ *TRIPLE-CHECK SIGNAL* ⚡\n"
            f"━━━━━━━━━━━━━━━\n"
            f"🧭 *Direction:* `{signal}`\n"
            f"💰 *Entry:* `${price:,.2f}`\n\n"
            f"📊 *PLAN (1:2 RR)*\n"
            f"🛑 *Stop Loss:* `${sl:,.2f}`\n"
            f"🎯 *Take Profit:* `${tp:,.2f}`\n\n"
            f"🧪 RSI: `{rsi:.1f}` | Trend: `Confirmed`"
        )
        await context.bot.send_message(CHAT_ID, msg, parse_mode='Markdown')
    elif now.minute == 0:
        await context.bot.send_message(CHAT_ID, f"✅ Bot Heartbeat: Scanning... BTC: ${price:,.2f}")

async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uptime = str(datetime.timedelta(seconds=int(time.time() - START_TIME)))
    await update.message.reply_text(f"🤖 *System Status:* Online\n⏳ *Uptime:* `{uptime}`", parse_mode='Markdown')

async def check(update: Update, context: ContextTypes.DEFAULT_TYPE):
    signal, price, sl, tp, rsi = get_confirmed_signals()
    status_text = f"Direction: {signal if signal else 'None'}\nPrice: ${price:,.2f}\nRSI: {rsi:.1f}"
    await update.message.reply_text(f"🔍 *Live Scan Results:*\n`{status_text}`", parse_mode='Markdown')

if __name__ == '__main__':
    application = ApplicationBuilder().token(TOKEN).build()
    application.add_handler(CommandHandler('status', status))
    application.add_handler(CommandHandler('check', check))
    application.job_queue.run_repeating(scanner_job, interval=60, first=5)
    application.run_polling(drop_pending_updates=True)
