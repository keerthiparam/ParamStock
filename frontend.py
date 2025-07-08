# frontend.py
import streamlit as st
import requests
import yaml
import time

# --- Configuration & Helper Functions ---
BACKEND_URL = "http://127.0.0.1:5000"
CONFIG_FILE = 'config.yaml'

# In frontend.py
def load_config():
    # Explicitly open the file with UTF-8 encoding
    with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)

def save_config(config):
    with open(CONFIG_FILE, 'w') as f:
        yaml.dump(config, f, default_flow_style=False)

# --- App Initialization & Onboarding ---
st.set_page_config(page_title="ParamStock", layout="centered")

config = load_config()
APP_CONFIG = config['app_config']
TWILIO_CONFIG = config['twilio']
USER_CONFIG = config['user']

# Function to check if all necessary configs are set
def is_configured():
    return all([TWILIO_CONFIG['account_sid'], TWILIO_CONFIG['auth_token'], TWILIO_CONFIG['phone_number'], USER_CONFIG['phone_number']])

# === ONBOARDING LOGIC ===
if not is_configured():
    st.title("👋 Welcome to ParamStock!")
    st.markdown("Let's get started.")

    # Step 1: Get Twilio Credentials
    st.header("Step 1: Connect to Twilio")
    st.markdown("This app uses Twilio to send free WhatsApp alerts. You'll need a free account.")
    st.link_button("Go to Twilio Console", "https://www.twilio.com/console")
    
    with st.expander("Where do I find these values?"):
        st.image("https://i.imgur.com/g0QhV3D.png", caption="Find your Account SID and Auth Token on your Twilio Dashboard.")

    new_sid = st.text_input("1. Your Account SID", value=TWILIO_CONFIG['account_sid'], placeholder="Starts with ACXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX")
    new_token = st.text_input("2. Your Auth Token", value=TWILIO_CONFIG['auth_token'], type="password")
    new_twilio_phone = st.text_input("3. Your Twilio Sandbox Number", value=TWILIO_CONFIG['phone_number'], placeholder="Format: whatsapp:+1XXXXXXXXXX")
    
    # Step 2: Get User's Phone Number
    st.header("Step 2: Your WhatsApp Number")
    new_user_phone = st.text_input("Enter your personal WhatsApp number", value=USER_CONFIG['phone_number'], placeholder="Format: +91XXXXXXXXXX")
    
    # Step 3: Save and Finish
    st.header("Step 3: Finish Setup")
    if st.button("Save Configuration"):
        config['twilio']['account_sid'] = new_sid
        config['twilio']['auth_token'] = new_token
        config['twilio']['phone_number'] = new_twilio_phone
        config['user']['phone_number'] = new_user_phone
        save_config(config)
        st.success("Configuration Saved! The app will now launch.")
        time.sleep(2)
        st.rerun()

    st.stop() # Stop the rest of the app until onboarding is done

# === MAIN APPLICATION UI ===
st.title(APP_CONFIG['title'])
st.sidebar.header(f"⚙️ Settings")
st.sidebar.success(f"**Alerts for:** {USER_CONFIG['phone_number']}")
st.sidebar.info(f"**Check Interval:** Every {APP_CONFIG['check_interval']} seconds")

col1, col2 = st.columns([1, 1.2])

with col1:
    st.header(APP_CONFIG['header'])
    
    search_term = st.text_input("Search for a stock", placeholder="e.g., Reliance, SBI, RVNL")
    
    results_placeholder = st.empty()

    if search_term:
        try:
            res = requests.get(f"{BACKEND_URL}/api/search", params={'query': search_term})
            search_results = res.json()
            if search_results:
                ticker_options = {f"{item['name']} ({item['symbol']})": item['symbol'] for item in search_results if item.get('name')}
                if ticker_options:
                    selected_display_name = results_placeholder.selectbox("Select the correct stock", options=list(ticker_options.keys()))
                    ticker = ticker_options[selected_display_name]
                    
                    st.success(f"Selected Ticker: **{ticker}**")
                    condition_label = st.selectbox("Alert me when", options=['Price is > (Above)', 'Price is < (Below)'])
                    target_price = st.number_input("Target Price", value=1.00, min_value=0.01, format="%.2f")
                    delete_on_trigger = st.checkbox("🗑️ One-time alert")
                    
                    if st.button("Set Alert", use_container_width=True, type="primary"):
                        payload = {"phone_number": USER_CONFIG['phone_number'], "ticker": ticker, "target_price": target_price,
                                   "condition": 'above' if '>' in condition_label else 'below', "delete_on_trigger": delete_on_trigger}
                        requests.post(f"{BACKEND_URL}/api/add_alert", json=payload)
                        st.success("✅ Alert set successfully!")
                        time.sleep(1)
                        st.rerun()
                else:
                    results_placeholder.info("No valid results found. Try a different name.")
            else:
                results_placeholder.info("No results found. Please try another search term.")
        except requests.ConnectionError:
            results_placeholder.error("Cannot connect to backend for search.")
    else:
        results_placeholder.info("Start typing above to search for a stock.")

with col2:
    st.header("‼️ Your Active Alerts")
    
    if st.button("🔄 Refresh Alerts", use_container_width=True):
        st.rerun()

    try:
        res = requests.get(f"{BACKEND_URL}/api/get_alerts/{USER_CONFIG['phone_number']}")
        alerts = res.json()
        if not alerts:
            st.info("You have no active alerts.")
        
        for alert in sorted(alerts, key=lambda x: x['ticker']):
            status = "🔔 Triggered" if alert['alert_sent'] else "Active"
            with st.container():
                c1, c2 = st.columns([4, 1])
                with c1:
                    st.markdown(f"**{alert['ticker']}** `{status}`\n\nTarget: Price {' > ' if alert['condition'] == 'above' else ' < '} **₹{alert['target_price']:.2f}**")
                with c2:
                    if st.button("❌", key=f"del_{alert['id']}", help="Delete this alert"):
                        requests.post(f"{BACKEND_URL}/api/delete_alert/{alert['id']}")
                        st.rerun()
                st.markdown("<hr>", unsafe_allow_html=True)
    except requests.ConnectionError:
        st.error("Could not connect to the backend server.")