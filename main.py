import os, time, asyncio, requests, datetime
import pandas as pd
import pandas_ta as ta
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

# --- CONFIG ---
TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
RR_RATIO = 2.0
START_TIME = time.time()

def get_market_analysis():
    url = "https://api.binance.com/api/v3/klines?symbol=BTCUSDT&interval=1m&limit=150"
    try:
        response = requests.get(url, timeout=10)
        if response.status_code != 200: return None, 0, 0, 0, 0, "⚠️ Binance API Error"
        
        data = response.json()
        df = pd.DataFrame(data, columns=['ts','o','h','l','c','v','ct','qv','nt','tb','tq','i'])
        df['c'] = df['c'].astype(float)
        
        ema200 = ta.ema(df['c'], length=200)
        rsi = ta.rsi(df['c'], length=14)
        macd = ta.macd(df['c'])
        
        if df.empty or ema200 is None: return None, 0, 0, 0, 0, "⚠️ Calculating..."
        
        curr_p = df['c'].iloc[-1]
        curr_rsi = rsi.iloc[-1]
        curr_ema200 = ema200.iloc[-1]
        trend = "📈 BULLISH" if curr_p > curr_ema200 else "📉 BEARISH"

        sl_dist = curr_p * 0.004
        tp_dist = sl_dist * RR_RATIO

        is_long = (curr_p > curr_ema200) and (macd['MACDh_12_26_9'].iloc[-1] > 0) and (50 < curr_rsi < 65)
        is_short = (curr_p < curr_ema200) and (macd['MACDh_12_26_9'].iloc[-1] < 0) and (35 < curr_rsi < 50)

        signal = "🟢 LONG" if is_long else "🔴 SHORT" if is_short else None
        return signal, curr_p, curr_p - sl_dist if is_long else curr_p + sl_dist, \
               curr_p + tp_dist if is_long else curr_p - tp_dist, curr_rsi, trend
            
    except Exception as e:
        return None, 0, 0, 0, 0, f"❌ Link Down: {str(e)[:15]}"

async def scanner_job(context: ContextTypes.DEFAULT_TYPE):
    signal, price, sl, tp, rsi, trend = get_market_analysis()
    now = datetime.datetime.now()
    if 30 <= now.minute <= 55 and signal:
        msg = (f"⚡ *TRIPLE-CHECK SIGNAL* ⚡\n"
               f"🧭 *Trade:* `{signal}`\n💰 *Price:* `${price:,.2f}`\n"
               f"🛑 *SL:* `${sl:,.2f}` | 🎯 *TP:* `${tp:,.2f}`")
        await context.bot.send_message(CHAT_ID, msg, parse_mode='Markdown')

async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    signal, price, _, _, rsi, trend = get_market_analysis()
    uptime = str(datetime.timedelta(seconds=int(time.time() - START_TIME)))
    
    # If price is 0, it means get_market_analysis returned an error
    status_msg = "✅ Operational" if price > 0 else "🛑 API Connection Issue"
    
    msg = (
        f"🤖 *LIVE BOT STATUS*\n━━━━━━━━━━━━━━━\n"
        f"💰 *BTC Price:* `${price:,.2f}`\n"
        f"🌊 *Trend:* `{trend}`\n"
        f"📉 *RSI:* `{rsi:.1f}`\n\n"
        f"⚙️ *System Stats:*\n"
        f"• Health: `{status_msg}`\n"
        f"• Uptime: `{uptime}`\n━━━━━━━━━━━━━━━"
    )
    await update.message.reply_text(msg, parse_mode='Markdown')

if __name__ == '__main__':
    # Initialize app
    application = ApplicationBuilder().token(TOKEN).build()
    
    # Add Command
    application.add_handler(CommandHandler('status', status))
    
    # Start Jobs
    application.job_queue.run_repeating(scanner_job, interval=60, first=10)
    
    print("Bot Starting...")
    # Clean start to prevent Conflict
    application.run_polling(drop_pending_updates=True, close_loop=False)
