# price_checker.py
import time
import yaml
import yfinance as yf
from twilio.rest import Client
from app import app, db, Alert

# --- Load Configuration from config.yaml ---
try:
    with open('config.yaml', 'r') as f:
        config = yaml.safe_load(f)
        
    TWILIO_CONFIG = config['twilio']
    APP_SETTINGS = config.get('app_settings', {'check_interval': 60}) # Use default if not set

    TWILIO_ACCOUNT_SID = TWILIO_CONFIG['account_sid']
    TWILIO_AUTH_TOKEN = TWILIO_CONFIG['auth_token']
    TWILIO_PHONE_NUMBER = TWILIO_CONFIG['phone_number']
    
    CHECK_INTERVAL = APP_SETTINGS.get('check_interval', 60)

except FileNotFoundError:
    print("ERROR: config.yaml not found. Please create it.")
    exit()
except KeyError as e:
    print(f"ERROR: Missing key in config.yaml: {e}")
    exit()
# ---------------------------------------------

# Initialize Twilio client
twilio_client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)

def get_stock_price(ticker_symbol):
    """Fetches the current market price of a stock."""
    try:
        stock = yf.Ticker(ticker_symbol)
        price = stock.info.get('regularMarketPrice') or stock.info.get('previousClose')
        if price: return price
        else:
            print(f"Could not fetch price for {ticker_symbol}. Check the ticker symbol.")
            return None
    except Exception as e:
        print(f"Error fetching data for {ticker_symbol}: {e}")
        return None

def send_whatsapp_alert(message, to_number):
    """Sends a message to a specific WhatsApp number using Twilio."""
    try:
        full_to_number = f"whatsapp:{to_number}"
        twilio_client.messages.create(
            body=message,
            from_=TWILIO_PHONE_NUMBER,
            to=full_to_number
        )
        print(f"WhatsApp alert sent to {to_number}")
    except Exception as e:
        print(f"Error sending WhatsApp message: {e}")

def check_all_alerts():
    """Main function to check stock prices and send alerts from the database."""
    print("--- Starting price check cycle ---")
    with app.app_context():
        active_alerts = Alert.query.filter_by(alert_sent=False).all()
        print(f"Found {len(active_alerts)} active alerts to check.")

        for alert in active_alerts:
            price = get_stock_price(alert.ticker)
            if price is None:
                continue
            
            print(f"Checking {alert.ticker} for {alert.phone_number}: Current=₹{price:.2f}, Target={alert.condition} ₹{alert.target_price:.2f}")

            alert_triggered = False
            if alert.condition == 'below' and price <= alert.target_price:
                alert_triggered = True
            elif alert.condition == 'above' and price >= alert.target_price:
                alert_triggered = True
            
            if alert_triggered:
                message = f"🚨 *Stock Alert!* 🚨\n\n*{alert.ticker}* is now at *₹{price:.2f}*.\nYour target was: *{alert.condition} ₹{alert.target_price:.2f}*."
                send_whatsapp_alert(message, alert.phone_number)
                alert.alert_sent = True
                db.session.commit()
    
    print("--- Price check cycle finished ---\n")

# Main loop
if __name__ == "__main__":
    print("🚀 Price Checker Started! Loading settings from config.yaml.")
    while True:
        check_all_alerts()
        print(f"Sleeping for {CHECK_INTERVAL} seconds...")
        time.sleep(CHECK_INTERVAL)