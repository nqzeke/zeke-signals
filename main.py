import os
import uuid
import requests
from flask import Flask, request

app = Flask(__name__)

# ─── ENV VARIABLES ───
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
CHAT_ID = os.environ.get("CHAT_ID")
DXTRADE_USERNAME = os.environ.get("DXTRADE_USERNAME")
DXTRADE_PASSWORD = os.environ.get("DXTRADE_PASSWORD")

DXTRADE_BASE = "https://dx.tradeifycrypto.co/dxsca-web"
ACCOUNT_CODE = "2138913"
RISK_DOLLARS = 3  # Change this anytime

# ─── TELEGRAM ───
def send_telegram(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    try:
        requests.post(url, json={"chat_id": CHAT_ID, "text": message, "parse_mode": "Markdown"}, timeout=10)
    except Exception as e:
        print(f"Telegram error: {e}")

# ─── DXTRADE AUTH ───
def get_dxtrade_token():
    url = f"{DXTRADE_BASE}/login"
    payload = {
        "username": DXTRADE_USERNAME,
        "password": DXTRADE_PASSWORD,
        "domain": os.environ.get("DXTRADE_DOMAIN", "default")
    }
    try:
        resp = requests.post(url, json=payload, timeout=10)
        resp.raise_for_status()
        token = resp.json().get("token")
        return token
    except Exception as e:
        print(f"DXTrade auth error: {e}")
        return None

# ─── PLACE ORDER ───
def place_order(token, direction, entry_price, sl, tp1):
    entry = float(entry_price)
    sl_price = float(sl)
    tp_price = float(tp1)

    # Calculate quantity based on $RISK_DOLLARS risk
    sl_distance = abs(entry - sl_price)
    if sl_distance == 0:
        print("SL distance is 0, skipping order")
        return None

    # For BTC/USD — quantity in BTC
    quantity = round(RISK_DOLLARS / sl_distance, 6)
    quantity = max(quantity, 0.0001)  # minimum order size

    side = "BUY" if direction.upper() == "LONG" else "SELL"
    order_id = str(uuid.uuid4())

    url = f"{DXTRADE_BASE}/accounts/{ACCOUNT_CODE}/orders"
    headers = {"Authorization": f"DXAPI {token}", "Content-Type": "application/json"}

    payload = {
        "clientOrderId": order_id,
        "type": "MARKET",
        "instrument": "BTC/USD",
        "side": side,
        "quantity": quantity,
        "stopLoss": sl_price,
        "takeProfit": tp_price
    }

    try:
        resp = requests.post(url, json=payload, headers=headers, timeout=10)
        print(f"Order response: {resp.status_code} — {resp.text}")
        return resp
    except Exception as e:
        print(f"Order placement error: {e}")
        return None

# ─── WEBHOOK ───
@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.json
    alert_type = data.get("type", "")
    symbol = data.get("symbol", "BTC/USD")
    price = data.get("price", "")
    timeframe = data.get("timeframe", "")
    direction = data.get("direction", "")
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

        # Place order on DXTrade
        token = get_dxtrade_token()
        if token:
            resp = place_order(token, direction, price, sl, tp1)
            if resp and resp.status_code in [200, 201]:
                send_telegram(f"✅ *Order placed successfully on DXTrade*\nDirection: {direction} | Risk: ${RISK_DOLLARS}")
            else:
                status = resp.status_code if resp else "no response"
                body = resp.text if resp else ""
                send_telegram(f"❌ *Order FAILED on DXTrade*\nStatus: {status}\n{body}")
        else:
            send_telegram("❌ *DXTrade auth failed — could not get token*")

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
    return "Zeke Signals Bot is running!", 200

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
