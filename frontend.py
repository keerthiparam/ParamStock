# frontend.py (Definitive, Stabilized Version)
import streamlit as st
import requests
import yaml
import time
from streamlit_searchbox import st_searchbox

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

# Reset function to avoid session state bugs
def reset_searchbox_state():
    st.session_state["stock_searchbox"] = {
        "options_js": [],
        "key_react": f"react-key-{time.time()}",
        "result": None,
        "search": ""  # 🔥 Add this line to avoid KeyError: 'search'
    }

# --- THE STABILIZED SEARCH FUNCTION ---
def search_tickers(search_term: str) -> list[tuple[str, str]]:
    if not search_term or len(search_term) < 2:
        return [("INFO", "Keep typing to search...")]
    try:
        res = requests.get(f"{BACKEND_URL}/api/search", params={'query': search_term})
        res.raise_for_status()
        search_results = res.json()
        formatted_results = [
            (item['symbol'], f"{item['name']} ({item['symbol']})")
            for item in search_results if item.get('name')
        ]
        if not formatted_results:
            return [("NO_RESULTS", "No stocks found, please try another search.")]
        return formatted_results
    except requests.exceptions.RequestException:
        return [("ERROR", "⚠️ Error connecting to the data source.")]
    except ValueError:
        return [("ERROR", "⚠️ Received invalid data from the server.")]

# --- App Initialization & Onboarding ---
st.set_page_config(page_title="ParamStock Alerter", layout="centered")

config = load_config()
APP_CONFIG = config['app_config']
TWILIO_CONFIG = config['twilio']
USER_CONFIG = config['user']

def is_configured():
    return all([
        TWILIO_CONFIG.get('account_sid'),
        TWILIO_CONFIG.get('auth_token'),
        TWILIO_CONFIG.get('phone_number'),
        USER_CONFIG.get('phone_number')
    ])

# === ONBOARDING LOGIC ===
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

    # Ensure searchbox state is properly initialized
    if "stock_searchbox" not in st.session_state or not isinstance(st.session_state["stock_searchbox"], dict):
        reset_searchbox_state()

    selected_ticker = st_searchbox(
        search_function=search_tickers,
        placeholder="Search for a stock (e.g., Reliance...)",
        label="Search and Select a Stock",
        key="stock_searchbox"
    )

    if selected_ticker and selected_ticker not in ["NO_RESULTS", "ERROR", "INFO"]:
        @st.cache_data(ttl=600)
        def get_details_for_ticker(ticker: str):
            try:
                res = requests.get(f"{BACKEND_URL}/api/search", params={'query': ticker})
                for item in res.json():
                    if item['symbol'] == ticker:
                        return item
            except:
                return None
        
        selected_stock_details = get_details_for_ticker(selected_ticker)

        if selected_stock_details:
            with st.container(border=True):
                st.markdown(f"**{selected_stock_details['name']}**")
                st.code(f"ID: {selected_stock_details['symbol']} | Exchange: {selected_stock_details['exchange']} | Type: {selected_stock_details['type']}")
        
        condition_label = st.selectbox("Alert me when...", options=['Price is ≥ (Above or Equal)', 'Price is ≤ (Below or Equal)'])
        target_price = st.number_input("Target Price", value=1.00, min_value=0.01, format="%.2f")
        delete_on_trigger = st.checkbox("🗑️ One-time alert")

        if st.button("Set Alert", use_container_width=True, type="primary"):
            payload = {
                "phone_number": USER_CONFIG['phone_number'],
                "ticker": selected_ticker,
                "target_price": target_price,
                "condition": 'above' if '≥' in condition_label else 'below',
                "delete_on_trigger": delete_on_trigger
            }
            try:
                requests.post(f"{BACKEND_URL}/api/add_alert", json=payload)
                st.success("✅ Alert set successfully!")
                reset_searchbox_state()
                time.sleep(1)
                st.rerun()
            except requests.ConnectionError:
                st.error("Could not connect to the backend.")

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
