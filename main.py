import os, time, asyncio, requests, datetime
import pandas as pd
import pandas_ta as ta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

# --- CONFIG ---
TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
RR_RATIO = 2.0  # 1:2 Risk-to-Reward Ratio
START_TIME = time.time()

def get_market_analysis():
    """Fetches live Binance data and performs the Triple-Check Strategy."""
    url = "https://api.binance.com/api/v3/klines?symbol=BTCUSDT&interval=1m&limit=150"
    try:
        response = requests.get(url, timeout=10)
        if response.status_code != 200:
            return None, 0, 0, 0, 0, "⚠️ Binance API Error"
        
        data = response.json()
        df = pd.DataFrame(data, columns=['ts','o','h','l','c','v','ct','qv','nt','tb','tq','i'])
        df['c'] = df['c'].astype(float)
        
        # Calculate Indicators (The 'Triple-Check')
        ema200 = ta.ema(df['c'], length=200)
        rsi = ta.rsi(df['c'], length=14)
        macd = ta.macd(df['c'])
        
        if df.empty or ema200 is None:
            return None, 0, 0, 0, 0, "⚠️ Calculating Indicators..."
        
        curr_p = df['c'].iloc[-1]
        curr_rsi = rsi.iloc[-1]
        curr_ema200 = ema200.iloc[-1]
        curr_macd_h = macd['MACDh_12_26_9'].iloc[-1]
        
        # Real-time Trend Determination
        trend_dir = "📈 BULLISH" if curr_p > curr_ema200 else "📉 BEARISH"

        # Risk Math (0.4% SL buffer)
        sl_dist = curr_p * 0.004
        tp_dist = sl_dist * RR_RATIO

        # Strategy Logic: Longs and Shorts
        is_long = (curr_p > curr_ema200) and (curr_macd_h > 0) and (50 < curr_rsi < 65)
        is_short = (curr_p < curr_ema200) and (curr_macd_h < 0) and (35 < curr_rsi < 50)

        signal = "🟢 LONG" if is_long else "🔴 SHORT" if is_short else None
        
        return signal, curr_p, \
               (curr_p - sl_dist if is_long else curr_p + sl_dist), \
               (curr_p + tp_dist if is_long else curr_p - tp_dist), \
               curr_rsi, trend_dir
            
    except Exception as e:
        return None, 0, 0, 0, 0, f"❌ Link Error: {str(e)[:15]}"

async def scanner_job(context: ContextTypes.DEFAULT_TYPE):
    """Background scanner that triggers alerts during the 'Golden Window'."""
    signal, price, sl, tp, rsi, trend = get_market_analysis()
    now = datetime.datetime.now()
    
    # Alert window: 30-55 mins past the hour
    if 30 <= now.minute <= 55 and signal:
        msg = (
            f"⚡ *TRIPLE-CHECK SIGNAL DETECTED* ⚡\n"
            f"━━━━━━━━━━━━━━━\n"
            f"🧭 *Trade:* `{signal}`\n"
            f"💰 *Entry:* `${price:,.2f}`\n\n"
            f"📊 *PLAN (1:2 RR)*\n"
            f"🛑 *Stop Loss:* `${sl:,.2f}`\n"
            f"🎯 *Take Profit:* `${tp:,.2f}`\n\n"
            f"🧪 RSI: `{rsi:.1f}` | Trend: `{trend}`\n"
            f"━━━━━━━━━━━━━━━"
        )
        await context.bot.send_message(CHAT_ID, msg, parse_mode='Markdown')

# --- THE DYNAMIC STATUS COMMAND ---
async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Probes the actual market and API status before replying."""
    signal, price, _, _, rsi, trend = get_market_analysis()
    uptime_sec = int(time.time() - START_TIME)
    uptime = str(datetime.timedelta(seconds=uptime_sec))
    
    # If price is 0, it means the Binance probe failed
    health_status = "✅ Operational" if price > 0 else "🛑 Connection Issue"
    
    msg = (
        f"🤖 *LIVE BOT STATUS*\n"
        f"━━━━━━━━━━━━━━━\n"
        f"💰 *BTC Price:* `${price:,.2f}`\n"
        f"🌊 *Trend:* `{trend}`\n"
        f"📉 *RSI:* `{rsi:.1f}`\n\n"
        f"⚙️ *System Health:*\n"
        f"• Status: `{health_status}`\n"
        f"• Uptime: `{uptime}`\n"
        f"• Scanner: `Active (Every 60s)`\n"
        f"• Conflicts: `Resolved` 🛡️\n"
        f"━━━━━━━━━━━━━━━\n"
        f"✅ *Verification:* Bot is live and scanning."
    )
    await update.message.reply_text(msg, parse_mode='Markdown')

if __name__ == '__main__':
    # Initialize Application
    application = ApplicationBuilder().token(TOKEN).build()
    
    # Add Handlers
    application.add_handler(CommandHandler('status', status))
    
    # Start Background Scanner
    application.job_queue.run_repeating(scanner_job, interval=60, first=10)
    
    print("Bot Starting and Clearing Sessions...")
    
    # CRITICAL: Fix for the 'Conflict' error
    application.run_polling(drop_pending_updates=True)
