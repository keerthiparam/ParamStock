# backend.py
import time
import yaml
import threading
import yfinance as yf
from flask import Flask, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from twilio.rest import Client
import os
import requests

# --- Configuration & Setup ---
CONFIG_FILE = 'config.yaml'

def load_config():
    with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)

config = load_config()
APP_CONFIG = config['app_config']
TWILIO_CONFIG = config['twilio']
CHECK_INTERVAL = APP_CONFIG['check_interval']

try:
    project_root = os.path.dirname(os.path.abspath(__file__))
    instance_path = os.path.join(project_root, 'instance')
    os.makedirs(instance_path, exist_ok=True)
except Exception as e: print(f"Error creating instance folder: {e}")

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{os.path.join(instance_path, "alerts.db")}'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# --- Database Model ---
class Alert(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_phone_number = db.Column(db.String(20), nullable=False)
    ticker = db.Column(db.String(20), nullable=False)
    target_price = db.Column(db.Float, nullable=False)
    condition = db.Column(db.String(10), nullable=False)
    delete_on_trigger = db.Column(db.Boolean, default=False, nullable=False)
    alert_sent = db.Column(db.Boolean, default=False, nullable=False)

# --- API Endpoints ---
@app.route('/api/add_alert', methods=['POST'])
def add_alert():
    data = request.get_json()
    new_alert = Alert(user_phone_number=data['phone_number'], ticker=data['ticker'].upper(), target_price=float(data['target_price']), condition=data['condition'], delete_on_trigger=data['delete_on_trigger'])
    db.session.add(new_alert)
    db.session.commit()
    return jsonify({'message': 'Alert created!'}), 201

@app.route('/api/get_alerts/<phone_number>')
def get_alerts(phone_number):
    # Trust the phone number received from the URL and use it directly.
    alerts = Alert.query.filter_by(user_phone_number=phone_number).all()
    
    return jsonify([{'id': a.id, 'ticker': a.ticker, 'target_price': a.target_price, 
                     'condition': a.condition, 'alert_sent': a.alert_sent} for a in alerts])

@app.route('/api/delete_alert/<int:alert_id>', methods=['POST'])
def delete_alert(alert_id):
    alert = Alert.query.get(alert_id)
    if alert:
        db.session.delete(alert)
        db.session.commit()
        return jsonify({'message': 'Alert deleted!'}), 200
    return jsonify({'error': 'Alert not found'}), 404

@app.route('/api/search')
def search_ticker():
    query = request.args.get('query', '')
    if not query: return jsonify([])
    
    url = f"https://query1.finance.yahoo.com/v1/finance/search?q={query}"
    headers = {'User-Agent': 'Mozilla/5.0'}
    
    try:
        # ADDED: A 5-second timeout to the request
        res = requests.get(url, headers=headers, timeout=5)
        res.raise_for_status() # This will raise an error if the response is bad (e.g., 404, 500)
        data = res.json()
        results = []
        for item in data.get('quotes', []):
            if 'symbol' in item and 'longname' in item:
                results.append({
                    'symbol': item['symbol'], 'name': item['longname'],
                    'exchange': item.get('exchDisp', 'N/A'),
                    'type': item.get('quoteType', 'N/A').capitalize()
                })
        return jsonify(results)
    except requests.exceptions.RequestException as e:
        # If anything goes wrong (timeout, network error), log it and return a specific error
        print(f"Backend Error: Failed to fetch from Yahoo API. Reason: {e}")
        return jsonify({"error": "Data provider is unavailable or slow to respond."}), 503 # 503 Service Unavailable

# --- Price Checker Logic ---
def price_checker_worker():
    print("Background Price Checker: Thread started.")
    if not all([TWILIO_CONFIG.get('account_sid'), TWILIO_CONFIG.get('auth_token'), TWILIO_CONFIG.get('phone_number')]):
        print("Checker: Twilio credentials incomplete. Checker will idle.")
        return
    twilio_client = Client(TWILIO_CONFIG['account_sid'], TWILIO_CONFIG['auth_token'])
    
    def get_stock_price(ticker):
        try: return yf.Ticker(ticker).info.get('regularMarketPrice')
        except Exception: return None

    while True:
        with app.app_context():
            active_alerts = Alert.query.filter_by(alert_sent=False).all()
            for alert in active_alerts:
                price = get_stock_price(alert.ticker)
                if not price: continue
                
                # FIXED: Logic now correctly uses > and < only
                triggered = (alert.condition == 'above' and price >= alert.target_price) or \
                            (alert.condition == 'below' and price <= alert.target_price)

                if triggered:
                    message = f"🚨 *Stock Alert!* 🚨\n\n*{alert.ticker}* is now at *₹{price:.2f}*."
                    try:
                        twilio_client.messages.create(body=message, from_=TWILIO_CONFIG['phone_number'], to=f"whatsapp:{alert.user_phone_number}")
                        print(f"Checker: Sent alert to {alert.user_phone_number}")
                    except Exception as e:
                        print(f"Checker: Error sending WhatsApp - {e}")
                    
                    if alert.delete_on_trigger:
                        db.session.delete(alert)
                    else:
                        alert.alert_sent = True
                    db.session.commit()
        time.sleep(CHECK_INTERVAL)

# --- Main Execution Block ---
if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    checker_thread = threading.Thread(target=price_checker_worker, daemon=True)
    checker_thread.start()
    print("🚀 Backend server starting...")
    app.run(port=5000, debug=True, use_reloader=False)