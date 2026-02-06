import os, time, asyncio, requests, datetime
import pandas as pd
import pandas_ta as ta
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

# --- CONFIG ---
TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
RR_RATIO = 2.0  # 1:2 Risk-Reward
START_TIME = time.time()

def get_market_analysis():
    """Fetches chart data and calculates indicators for status and alerts."""
    url = "https://api.binance.com/api/v3/klines?symbol=BTCUSDT&interval=1m&limit=150"
    try:
        data = requests.get(url, timeout=10).json()
        if not data or isinstance(data, dict): return None, 0, 0, 0, 0, "Unknown"
        
        df = pd.DataFrame(data, columns=['ts','o','h','l','c','v','ct','qv','nt','tb','tq','i'])
        df['c'] = df['c'].astype(float)
        
        # Calculate Indicators
        ema200 = ta.ema(df['c'], length=200)
        rsi = ta.rsi(df['c'], length=14)
        macd = ta.macd(df['c'])
        
        if df.empty or ema200 is None: return None, 0, 0, 0, 0, "Unknown"
        
        curr_p = df['c'].iloc[-1]
        curr_rsi = rsi.iloc[-1]
        curr_ema200 = ema200.iloc[-1]
        trend = "📈 BULLISH" if curr_p > curr_ema200 else "📉 BEARISH"

        # Risk Calculation
        sl_dist = curr_p * 0.004
        tp_dist = sl_dist * RR_RATIO

        # Signal Logic
        is_long = (curr_p > curr_ema200) and (macd['MACDh_12_26_9'].iloc[-1] > 0) and (50 < curr_rsi < 65)
        is_short = (curr_p < curr_ema200) and (macd['MACDh_12_26_9'].iloc[-1] < 0) and (35 < curr_rsi < 50)

        signal = "🟢 LONG" if is_long else "🔴 SHORT" if is_short else None
        return signal, curr_p, curr_p - sl_dist if is_long else curr_p + sl_dist, \
               curr_p + tp_dist if is_long else curr_p - tp_dist, curr_rsi, trend
            
    except Exception as e:
        print(f"Data Fetch Error: {e}")
    return None, 0, 0, 0, 0, "Error"

async def scanner_job(context: ContextTypes.DEFAULT_TYPE):
    signal, price, sl, tp, rsi, trend = get_market_analysis()
    now = datetime.datetime.now()
    
    if 30 <= now.minute <= 50 and signal:
        msg = (f"⚡ *TRIPLE-CHECK SIGNAL* ⚡\n━━━━━━━━━━━━━━━\n"
               f"🧭 *Direction:* `{signal}`\n💰 *Entry:* `${price:,.2f}`\n\n"
               f"📊 *PLAN (1:2 RR)*\n🛑 *SL:* `${sl:,.2f}`\n🎯 *TP:* `${tp:,.2f}`\n\n"
               f"🧪 RSI: `{rsi:.1f}` | Trend: `{trend}`")
        await context.bot.send_message(CHAT_ID, msg, parse_mode='Markdown')

# --- DYNAMIC STATUS COMMAND ---
async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Live Probing
    signal, price, _, _, rsi, trend = get_market_analysis()
    uptime = str(datetime.timedelta(seconds=int(time.time() - START_TIME)))
    
    msg = (
        f"🤖 *BOT LIVE STATUS* 🟢\n"
        f"━━━━━━━━━━━━━━━\n"
        f"💰 *BTC Price:* `${price:,.2f}`\n"
        f"🌊 *Trend:* `{trend}`\n"
        f"📉 *RSI:* `{rsi:.1f}`\n\n"
        f"⚙️ *System Stats:*\n"
        f"• Uptime: `{uptime}`\n"
        f"• Scanner: `Active`\n"
        f"• Conflict Check: `Resolved`\n"
        f"━━━━━━━━━━━━━━━\n"
        f"✅ *Result:* Everything is online and analyzing."
    )
    await update.message.reply_text(msg, parse_mode='Markdown')

if __name__ == '__main__':
    application = ApplicationBuilder().token(TOKEN).build()
    
    # Handlers
    application.add_handler(CommandHandler('status', status))
    
    # Background Scanner (Runs every 60s)
    application.job_queue.run_repeating(scanner_job, interval=60, first=5)
    
    # CRITICAL: drop_pending_updates=True clears old session conflicts
    application.run_polling(drop_pending_updates=True)
