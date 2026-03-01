
import os
import socket
import requests
from flask import Flask, request

app = Flask(__name__)

# ─── ENV VARIABLES ───
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
CHAT_ID = os.environ.get("CHAT_ID")

# ─── NINJATRADER ATI CONFIG ───
NT_HOST = os.environ.get("NT_HOST", "YOUR_PC_IP_HERE")  # Your PC's public IP
NT_PORT = int(os.environ.get("NT_PORT", 36973))
NT_ACCOUNT = os.environ.get("NT_ACCOUNT", "DEMO4530903")
RISK_DOLLARS = 3  # Change this anytime

# MGC tick value = $1 per 0.1 point, so $10 per full point
# 1 contract = $10/point
MGC_DOLLARS_PER_POINT = 10

# ─── TELEGRAM ───
def send_telegram(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    try:
        requests.post(url, json={"chat_id": CHAT_ID, "text": message, "parse_mode": "Markdown"}, timeout=10)
    except Exception as e:
        print(f"Telegram error: {e}")

# ─── NINJATRADER ATI ORDER ───
def place_nt_order(direction, entry_price, sl, tp1):
    entry = float(entry_price)
    sl_price = float(sl)
    tp_price = float(tp1)

    sl_distance = abs(entry - sl_price)
    if sl_distance == 0:
        print("SL distance is 0, skipping")
        return False

    # Calculate contracts based on risk
    risk_per_contract = sl_distance * MGC_DOLLARS_PER_POINT
    contracts = max(1, round(RISK_DOLLARS / risk_per_contract))

    action = "BUY" if direction.upper() in ["LONG", "BUY"] else "SELL"

    # NinjaTrader ATI command format
    # PLACE;<account>;<instrument>;<action>;<qty>;<order_type>;<limit_price>;<stop_price>;<TIF>;<oco_id>;<order_id>;<template>
    order_id = f"CY{int(entry_price)}"
    nt_command = f"PLACE;{NT_ACCOUNT};MGC APR26;{action};{contracts};MARKET;0;0;DAY;;{order_id};\n"

    # SL order
    sl_action = "SELL" if action == "BUY" else "BUY"
    sl_command = f"PLACE;{NT_ACCOUNT};MGC APR26;{sl_action};{contracts};STOP;0;{sl_price};DAY;;{order_id}SL;\n"

    # TP order
    tp_command = f"PLACE;{NT_ACCOUNT};MGC APR26;{sl_action};{contracts};LIMIT;{tp_price};0;DAY;;{order_id}TP;\n"

    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(5)
            s.connect((NT_HOST, NT_PORT))
            s.sendall(nt_command.encode())
            s.sendall(sl_command.encode())
            s.sendall(tp_command.encode())
        print(f"NT order sent: {action} {contracts} MGC @ market")
        return True, contracts
    except Exception as e:
        print(f"NinjaTrader ATI error: {e}")
        return False, 0

# ─── WEBHOOK ───
@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.json
    alert_type = data.get("type", "")
    symbol = data.get("symbol", "MGC")
    price = data.get("price", "")
    timeframe = data.get("timeframe", "")
    direction = data.get("direction", "") or data.get("side", "")
    sl = data.get("sl", "")
    tp1 = data.get("tp1", "")
    tp2 = data.get("tp2", "")

    if alert_type == "entry":
        # Send Telegram alert
        message = (
            f"🚨 *ENTRY SIGNAL — {symbol}*\n"
            f"Direction: *{direction}*\n"
            f"Entry: *{price}*\n"
            f"🔴 SL: {sl}\n"
            f"🟡 TP1: {tp1}\n"
            f"🟢 TP2: {tp2}\n"
            f"💰 Risk: ${RISK_DOLLARS}\n"
            f"*EXECUTE YOUR EDGE. 1 OF 1000.*"
        )
        send_telegram(message)

        # Place order on NinjaTrader
        success, contracts = place_nt_order(direction, price, sl, tp1)
        if success:
            send_telegram(f"✅ *Order placed on NinjaTrader Sim*\nDirection: {direction} | Contracts: {contracts} | Risk: ${RISK_DOLLARS}")
        else:
            send_telegram(f"❌ *NinjaTrader order FAILED — check Railway logs*\nMake sure AT Interface is enabled and NT_HOST is set correctly")

    elif alert_type == "watch":
        message = (
            f"👀 *WATCH ALERT — {symbol}*\n"
            f"Price pulling into {timeframe} FVG\n"
            f"Price: {price}\n"
            f"Wait for iFVG confirmation before entry."
        )
        send_telegram(message)

    else:
        send_telegram(f"📡 Alert received: {data}")

    return {"status": "ok"}, 200

@app.route("/")
def home():
    return "Cypher Gold Bot is running!", 200

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
