import os
import socket
import requests
from flask import Flask, request, jsonify

app = Flask(__name__)

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
CHAT_ID = os.environ.get("CHAT_ID")
WEBHOOK_SECRET = os.environ.get("WEBHOOK_SECRET", "cypher2026")
SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://rxtfknsbssaizndsfohd.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")
NT_HOST = os.environ.get("NT_HOST", "YOUR_PC_IP_HERE")
NT_PORT = int(os.environ.get("NT_PORT", 36973))
NT_ACCOUNT = os.environ.get("NT_ACCOUNT", "DEMO4530903")
RISK_DOLLARS = 160
MGC_DOLLARS_PER_POINT = 1

def supabase_insert(table, data):
    url = f"{SUPABASE_URL}/rest/v1/{table}"
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=representation"
    }
    try:
        r = requests.post(url, json=data, headers=headers, timeout=5)
        result = r.json()
        print(f"Supabase insert result: {result}")
        return result
    except Exception as e:
        print(f"Supabase insert error: {e}")
        return None

def supabase_update(table, signal_id, data):
    url = f"{SUPABASE_URL}/rest/v1/{table}?id=eq.{signal_id}"
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json"
    }
    try:
        r = requests.patch(url, json=data, headers=headers, timeout=5)
        return r.status_code
    except Exception as e:
        print(f"Supabase update error: {e}")
        return None

def validate_api_key(api_key):
    if not api_key:
        return False
    url = f"{SUPABASE_URL}/rest/v1/subscribers?api_key=eq.{api_key}&active=eq.true"
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}"
    }
    try:
        r = requests.get(url, headers=headers, timeout=5)
        result = r.json()
        return isinstance(result, list) and len(result) > 0
    except:
        return False

def send_telegram(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    try:
        r = requests.post(url, json={"chat_id": CHAT_ID, "text": message, "parse_mode": "Markdown"}, timeout=10)
        print(f"Telegram: {r.status_code}")
    except Exception as e:
        print(f"Telegram error: {e}")

def place_nt_order(direction, entry_price, sl, tp1):
    entry = float(entry_price)
    sl_price = float(sl)
    tp_price = float(tp1)
    sl_distance = abs(entry - sl_price)
    if sl_distance == 0:
        return False, 0, 0
    risk_per_contract = sl_distance * MGC_DOLLARS_PER_POINT
    contracts = max(1, int(RISK_DOLLARS / risk_per_contract))
    actual_risk = contracts * risk_per_contract
    action = "BUY" if direction.upper() in ["LONG", "BUY"] else "SELL"
    sl_action = "SELL" if action == "BUY" else "BUY"
    order_id = f"CY{int(entry)}"
    nt_command = f"PLACE;{NT_ACCOUNT};MGC APR26;{action};{contracts};MARKET;0;0;DAY;;{order_id};\n"
    sl_command = f"PLACE;{NT_ACCOUNT};MGC APR26;{sl_action};{contracts};STOP;0;{sl_price};DAY;;{order_id}SL;\n"
    tp_command = f"PLACE;{NT_ACCOUNT};MGC APR26;{sl_action};{contracts};LIMIT;{tp_price};0;DAY;;{order_id}TP;\n"
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(5)
            s.connect((NT_HOST, NT_PORT))
            s.sendall(nt_command.encode())
            s.sendall(sl_command.encode())
            s.sendall(tp_command.encode())
        return True, contracts, actual_risk
    except Exception as e:
        print(f"NinjaTrader ATI error: {e}")
        return False, 0, 0

@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.json
    if data.get("secret") != WEBHOOK_SECRET:
        return jsonify({"error": "unauthorized"}), 401
    alert_type = data.get("type", "")
    symbol = data.get("symbol", "MGC")
    price = data.get("price", "")
    timeframe = data.get("timeframe", "")
    direction = data.get("direction", "") or data.get("side", "")
    sl = data.get("sl", "")
    tp1 = data.get("tp1", "")
    tp2 = data.get("tp2", "")
    grade = data.get("grade", "A+")

    if alert_type == "entry":
        # Always save as pending so subscribers can pick it up
        signal_data = {
            "direction": direction,
            "symbol": symbol,
            "entry_price": float(price) if price else None,
            "sl": float(sl) if sl else None,
            "tp1": float(tp1) if tp1 else None,
            "tp2": float(tp2) if tp2 else None,
            "grade": grade,
            "status": "pending"
        }
        result = supabase_insert("signals", signal_data)
        signal_id = None
        if result and isinstance(result, list) and len(result) > 0:
            signal_id = result[0].get("id")

        message = (
            f"🚨 *ENTRY SIGNAL — {symbol}*\n"
            f"Direction: *{direction}*\n"
            f"Entry: *{price}*\n"
            f"🔴 SL: {sl}\n"
            f"🟡 TP1: {tp1}\n"
            f"🟢 TP2: {tp2}\n"
            f"Grade: *{grade}*\n"
            f"💰 Fixed Risk: ${RISK_DOLLARS}\n"
            f"*EXECUTE YOUR EDGE. 1 OF 1000.*"
        )
        send_telegram(message)

        # Try to execute YOUR trade via ngrok — stays pending for subscribers regardless
        success, contracts, actual_risk = place_nt_order(direction, price, sl, tp1)
        if success:
            send_telegram(f"✅ *Order placed on NinjaTrader*\n{direction} | {contracts} contracts | Risk: ${actual_risk:.2f}")
        else:
            send_telegram(f"❌ *NinjaTrader order FAILED — check Railway logs*")

        # Signal stays as "pending" so subscribers can still poll and execute it

    elif alert_type == "watch":
        send_telegram(f"👀 *WATCH ALERT — {symbol}*\nPrice pulling into {timeframe} FVG\nPrice: {price}\nWait for iFVG confirmation before entry.")
    else:
        send_telegram(f"📡 Alert received: {data}")

    return jsonify({"status": "ok"}), 200

@app.route("/signals/latest", methods=["GET"])
def get_latest_signal():
    api_key = request.headers.get("X-API-Key")
    if not validate_api_key(api_key):
        return jsonify({"error": "invalid api key"}), 401
    url = f"{SUPABASE_URL}/rest/v1/signals?status=eq.pending&order=created_at.desc&limit=1"
    headers = {"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}"}
    try:
        r = requests.get(url, headers=headers, timeout=5)
        signals = r.json()
        if isinstance(signals, list) and len(signals) > 0:
            return jsonify(signals[0]), 200
        return jsonify({"status": "no signal"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/signals/pulled", methods=["POST"])
def signal_pulled():
    api_key = request.headers.get("X-API-Key")
    if not validate_api_key(api_key):
        return jsonify({"error": "invalid api key"}), 401
    data = request.json
    signal_id = data.get("signal_id")
    if not signal_id:
        return jsonify({"error": "no signal_id"}), 400
    supabase_update("signals", signal_id, {"status": "pulled"})
    return jsonify({"status": "ok"}), 200

@app.route("/")
def home():
    return "Cypher Gold Bot is running!", 200

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
