# frontend.py
import streamlit as st
import requests
import yaml
import time

# --- Configuration & Helper Functions ---
BACKEND_URL = "http://127.0.0.1:5000"
CONFIG_FILE = 'config.yaml'

@st.cache_data
def load_config():
    with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)

def save_config(config):
    with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
        yaml.dump(config, f, default_flow_style=False)

@st.cache_data(ttl=300)
def fetch_search_results(search_term: str) -> dict: # Now returns a dictionary
    if not search_term:
        return {"data": []} # Return in a consistent format
    try:
        res = requests.get(f"{BACKEND_URL}/api/search", params={'query': search_term})
        response_data = res.json()
        # Check if the backend returned an error message
        if 'error' in response_data:
            return {"error": response_data['error']}
        return {"data": response_data}
    except (requests.ConnectionError, requests.exceptions.JSONDecodeError):
        # Handle cases where the backend is completely down
        return {"error": "Cannot connect to the backend server."}

# --- App Initialization & State Management ---
st.set_page_config(page_title="ParamStock Alerter", layout="centered")

config = load_config()
APP_CONFIG = config['app_config']
TWILIO_CONFIG = config['twilio']
USER_CONFIG = config['user']

if 'selected_stock' not in st.session_state:
    st.session_state.selected_stock = None

def is_configured():
    return all([TWILIO_CONFIG.get('account_sid'), TWILIO_CONFIG.get('auth_token'), TWILIO_CONFIG.get('phone_number'), USER_CONFIG.get('phone_number')])

# === ONBOARDING LOGIC (No changes needed) ===
if not is_configured():
    st.title("👋 Welcome to the Smart Stock Alerter!")
    st.markdown("Let's get you set up in a few simple steps.")
    st.header("Step 1: Connect to Twilio")
    st.link_button("Go to Twilio Console", "https://www.twilio.com/console")
    new_sid = st.text_input("1. Your Account SID", value=TWILIO_CONFIG.get('account_sid', ''), placeholder="Starts with AC...")
    new_token = st.text_input("2. Your Auth Token", value=TWILIO_CONFIG.get('auth_token', ''), type="password")
    new_twilio_phone = st.text_input("3. Your Twilio Sandbox Number", value=TWILIO_CONFIG.get('phone_number', ''), placeholder="Format: whatsapp:+1...")
    st.header("Step 2: Your WhatsApp Number")
    new_user_phone = st.text_input("Enter your personal WhatsApp number", value=USER_CONFIG.get('phone_number', ''), placeholder="Format: +91...")
    st.header("Step 3: Finish Setup")
    if st.button("Save Configuration & Start App"):
        config['twilio']['account_sid'] = new_sid
        config['twilio']['auth_token'] = new_token
        config['twilio']['phone_number'] = new_twilio_phone
        config['user']['phone_number'] = new_user_phone
        save_config(config)
        st.success("Configuration Saved! The app will now launch.")
        time.sleep(2)
        st.rerun()
    st.stop()

# === MAIN APPLICATION UI ===
st.title(APP_CONFIG['title'])
st.sidebar.header(f"⚙️ Settings")
st.sidebar.success(f"**Alerts for:** {USER_CONFIG['phone_number']}")
st.sidebar.info(f"**Check Interval:** Every {APP_CONFIG['check_interval']} seconds")

col1, col2 = st.columns([1, 1.2])

with col1:
    st.header(APP_CONFIG['header'])

    # --- THE "SINGLE WIDGET ILLUSION" IMPLEMENTATION ---
    if not st.session_state.selected_stock:
        search_term = st.text_input("Search for a stock...", placeholder="e.g., Reliance, SBI, Apple")
        results_container = st.empty()

        if search_term:
            # The search function now returns a dictionary with 'data' or 'error'
            result_payload = fetch_search_results(search_term)

            if "error" in result_payload:
                results_container.error(f"⚠️ {result_payload['error']}")
            
            elif result_payload.get("data"):
                search_results = result_payload["data"]
                with results_container.container():
                    st.write("---")
                    st.write("**Search Results:**")
                    for item in search_results:
                        if item.get('name'):
                            if st.button(f"{item['name']} ({item['symbol']})", use_container_width=True, key=item['symbol']):
                                st.session_state.selected_stock = item
                                st.rerun()
            else:
                results_container.info("No results found.")
    
    else: # This block runs only AFTER a stock is selected
        details = st.session_state.selected_stock
        with st.container(border=True):
            st.markdown(f"**{details['name']}**")
            st.code(f"ID: {details['symbol']} | Exchange: {details['exchange']} | Type: {details['type']}")

        # FIXED: Conditions now correctly reflect the backend logic
        condition_label = st.selectbox("Alert me when...", options=['Price is ≥ (Above)', 'Price is ≤ (Below)'])
        target_price = st.number_input("Target Price", value=1.00, min_value=0.01, format="%.2f")
        delete_on_trigger = st.checkbox("🗑️ One-time alert")

        c1_form, c2_form = st.columns(2)
        with c1_form:
            if st.button("Set Alert", use_container_width=True, type="primary"):
                condition_value = 'above' if 'Above' in condition_label else 'below'
                payload = {"phone_number": USER_CONFIG['phone_number'], "ticker": details['symbol'], 
                           "target_price": target_price, "condition": condition_value,
                           "delete_on_trigger": delete_on_trigger}
                try:
                    requests.post(f"{BACKEND_URL}/api/add_alert", json=payload)
                    st.success("✅ Alert set successfully!")
                    st.session_state.selected_stock = None
                    time.sleep(1)
                    st.rerun()
                except requests.ConnectionError:
                    st.error("Could not connect to the backend.")
        with c2_form:
            if st.button("Clear Selection", use_container_width=True):
                st.session_state.selected_stock = None
                st.rerun()

with col2:
    st.header("‼️ Your Active Alerts")
    if st.button("🔄 Refresh Alerts", use_container_width=True):
        st.rerun()
    try:
        clean_phone = USER_CONFIG['phone_number']
        res = requests.get(f"{BACKEND_URL}/api/get_alerts/{clean_phone}")
        alerts = res.json()
        if not alerts:
            st.info("You have no active alerts.")
        for alert in sorted(alerts, key=lambda x: x['ticker']):
            status = "🔔 Triggered" if alert['alert_sent'] else "Active"
            with st.container():
                c1_alert, c2_alert = st.columns([4, 1])
                with c1_alert:
                    st.markdown(f"**{alert['ticker']}** `{status}`\n\nTarget: Price {' ≥ ' if alert['condition'] == 'above' else ' ≤ '} **₹{alert['target_price']:.2f}**")
                with c2_alert:
                    if st.button("❌", key=f"del_{alert['id']}", help="Delete this alert"):
                        requests.post(f"{BACKEND_URL}/api/delete_alert/{alert['id']}")
                        st.rerun()
                st.markdown("<hr>", unsafe_allow_html=True)
    except requests.ConnectionError:
        st.error("Could not connect to the backend server.")