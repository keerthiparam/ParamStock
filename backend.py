# backend.py
import time
import yaml
import threading
import yfinance as yf
from flask import Flask, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from twilio.rest import Client
import os
import requests # Need this for the search API

# --- Load Configuration ---
with open('config.yaml', 'r') as f:
    config = yaml.safe_load(f)
TWILIO_CONFIG = config['twilio']
CHECK_INTERVAL = config.get('app_settings', {}).get('check_interval', 60)

# --- Auto-create the instance folder ---
try:
    project_root = os.path.dirname(os.path.abspath(__file__))
    instance_path = os.path.join(project_root, 'instance')
    os.makedirs(instance_path, exist_ok=True)
except Exception as e:
    print(f"Error creating instance folder: {e}")

# --- Flask App and Database Setup ---
app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{os.path.join(instance_path, "alerts.db")}'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# --- Upgraded Database Model ---
class Alert(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    phone_number = db.Column(db.String(20), nullable=False)
    ticker = db.Column(db.String(20), nullable=False)
    target_price = db.Column(db.Float, nullable=False)
    condition = db.Column(db.String(10), nullable=False) # 'above' or 'below'
    delete_on_trigger = db.Column(db.Boolean, default=False, nullable=False)
    alert_sent = db.Column(db.Boolean, default=False, nullable=False)

# --- API Endpoints ---
@app.route('/api/add_alert', methods=['POST'])
def add_alert():
    data = request.get_json()
    new_alert = Alert(
        phone_number=data['phone_number'], ticker=data['ticker'].upper(),
        target_price=float(data['target_price']), condition=data['condition'],
        delete_on_trigger=data['delete_on_trigger']
    )
    db.session.add(new_alert)
    db.session.commit()
    return jsonify({'message': 'Alert created!'}), 201

@app.route('/api/get_alerts/<phone_number>')
def get_alerts(phone_number):
    alerts = Alert.query.filter_by(phone_number=phone_number).all()
    return jsonify([{'id': a.id, 'ticker': a.ticker, 'target_price': a.target_price, 'condition': a.condition, 'alert_sent': a.alert_sent} for a in alerts])

@app.route('/api/delete_alert/<int:alert_id>', methods=['POST'])
def delete_alert(alert_id):
    alert = Alert.query.get(alert_id)
    if alert:
        db.session.delete(alert)
        db.session.commit()
        return jsonify({'message': 'Alert deleted!'}), 200
    return jsonify({'error': 'Alert not found'}), 404

# NEW: API endpoint to search for stock tickers
@app.route('/api/search')
def search_ticker():
    query = request.args.get('query', '')
    if not query:
        return jsonify([])
    
    # Use Yahoo Finance's unofficial search API
    url = f"https://query1.finance.yahoo.com/v1/finance/search?q={query}"
    headers = {'User-Agent': 'Mozilla/5.0'} # Pretend to be a browser
    try:
        res = requests.get(url, headers=headers)
        data = res.json()
        results = []
        for item in data.get('quotes', []):
            if 'symbol' in item and 'longname' in item:
                results.append({'symbol': item['symbol'], 'name': item['longname']})
        return jsonify(results)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# --- Price Checker Logic ---
def price_checker_worker():
    print("Background Price Checker: Thread started.")
    twilio_client = Client(TWILIO_CONFIG['account_sid'], TWILIO_CONFIG['auth_token'])
    
    def get_stock_price(ticker):
        try:
            stock = yf.Ticker(ticker)
            return stock.info.get('regularMarketPrice') or stock.info.get('previousClose')
        except Exception as e:
            print(f"Error fetching price for {ticker}: {e}")
            return None

    def send_whatsapp_alert(message, to_number):
        try:
            twilio_client.messages.create(
                body=message, from_=TWILIO_CONFIG['phone_number'], to=f"whatsapp:{to_number}"
            )
            print(f"Checker: Sent alert to {to_number}")
        except Exception as e:
            print(f"Checker: Error sending WhatsApp - {e}")

    while True:
        with app.app_context():
            active_alerts = Alert.query.filter_by(alert_sent=False).all()
            
            for alert in active_alerts:
                price = get_stock_price(alert.ticker)
                if not price: continue
                
                # UPDATED: Simplified condition logic
                triggered = False
                if alert.condition == 'above' and price > alert.target_price: triggered = True
                elif alert.condition == 'below' and price < alert.target_price: triggered = True

                if triggered:
                    message = f"🚨 *Stock Alert!* 🚨\n\n*{alert.ticker}* is now at *₹{price:.2f}*."
                    send_whatsapp_alert(message, alert.phone_number)
                    
                    if alert.delete_on_trigger:
                        db.session.delete(alert)
                    else:
                        alert.alert_sent = True # Corrected from 'sent'
                    db.session.commit()
        time.sleep(CHECK_INTERVAL)

# --- Main Execution Block ---
if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    checker_thread = threading.Thread(target=price_checker_worker, daemon=True)
    checker_thread.start()
    print("🚀 Backend server starting... Access the web app via frontend.py.")
    app.run(port=5000, debug=True, use_reloader=False)