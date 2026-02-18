import os
from flask import Flask, request
import requests

app = Flask(__name__)

TELEGRAM_TOKEN = "8205898881:AAH4uk_3Q3mR-DcWXrcj6iP9ZFRgihEM38M"
CHAT_ID = "8054275440"

def send_telegram(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    requests.post(url, json={"chat_id": CHAT_ID, "text": message, "parse_mode": "Markdown"})

@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.json
    alert_type = data.get("type", "")
    symbol = data.get("symbol", "BTC/USD")
    price = data.get("price", "")
    timeframe = data.get("timeframe", "")
    direction = data.get("direction", "")

    if alert_type == "watch":
        message = (
            f"👀 *WATCH ALERT — {symbol}*\n"
            f"Price pulling into {timeframe} FVG\n"
            f"Price: {price}\n"
            f"Wait for iFVG confirmation before entry."
        )
    elif alert_type == "entry":
        message = (
            f"🚨 *ENTRY SIGNAL — {symbol}*\n"
            f"Direction: *{direction}*\n"
            f"Entry: *{price}*\n"
            f"🔴 SL: {data.get('sl', 'N/A')}\n"
            f"🟡 TP1: {data.get('tp1', 'N/A')}\n"
            f"🟢 TP2: {data.get('tp2', 'N/A')}\n"
            f"*EXECUTE YOUR EDGE. 1 OF 1000.*"
        )
    else:
        message = f"📡 Alert received: {data}"

    send_telegram(message)
    return {"status": "ok"}, 200

@app.route("/")
def home():
    return "Zeke Signals Bot is running!", 200

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
