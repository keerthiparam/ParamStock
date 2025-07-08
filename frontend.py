# frontend.py
import streamlit as st
import requests
import yaml

# --- Configuration & Helper Functions ---
BACKEND_URL = "http://127.0.0.1:5000"
CONFIG_FILE = 'config.yaml'

def load_config():
    with open(CONFIG_FILE, 'r') as f:
        return yaml.safe_load(f)

def save_config(config):
    with open(CONFIG_FILE, 'w') as f:
        yaml.dump(config, f, default_flow_style=False)

# --- App Initialization & Single-User Setup ---
st.set_page_config(page_title="ParamStock Alerter", layout="wide")
st.title("📈 Smart Stock Alerter")

config = load_config()
phone_number = config.get('user', {}).get('phone_number')

if not phone_number:
    st.warning("First-Time Setup: Please enter your details.")
    new_phone = st.text_input("Your WhatsApp Number (e.g., +919876543210)")
    if st.button("Save Number"):
        if new_phone and new_phone.startswith('+'):
            config['user']['phone_number'] = new_phone
            save_config(config)
            st.success("Phone number saved! The app will now reload.")
            st.rerun()
        else:
            st.error("Please enter a valid number starting with a country code (+).")
    st.stop() # Stop the rest of the app from running until setup is complete

# --- Main App Interface ---
st.sidebar.header(f"⚙️ Settings")
st.sidebar.success(f"**Logged In As:**\n\n{phone_number}")

col1, col2 = st.columns([1, 1.2]) # Make the right column slightly wider

with col1:
    st.header("➕ Set a New Alert")
    
    # NEW: Ticker search functionality
    search_term = st.text_input("Search for a stock (e.g., Reliance, SBI, Apple)")
    if search_term:
        try:
            res = requests.get(f"{BACKEND_URL}/api/search", params={'query': search_term})
            search_results = res.json()
            if search_results:
                # Format for display: "Name (SYMBOL)"
                ticker_options = {f"{item['name']} ({item['symbol']})": item['symbol'] for item in search_results}
                selected_display_name = st.selectbox("Select the correct stock", options=list(ticker_options.keys()))
                ticker = ticker_options[selected_display_name]
            else:
                st.info("No results found. Please try another search term.")
                ticker = None
        except requests.ConnectionError:
            st.error("Cannot connect to backend for search.")
            ticker = None
    else:
        ticker = None
        st.info("Start typing above to search for a stock.")

    # Only show the rest of the form if a ticker has been selected
    if ticker:
        st.success(f"Selected Ticker: **{ticker}**")
        
        # UPDATED: Simplified conditions
        condition_options = {'Price is > (Above)': 'above', 'Price is < (Below)': 'below'}
        condition_label = st.selectbox("Alert me when...", options=list(condition_options.keys()))
        
        # UPDATED: Better default price
        target_price = st.number_input("Target Price", value=1.00, min_value=0.01, format="%.2f")
        delete_on_trigger = st.checkbox("🗑️ One-time alert (deletes itself after triggering)")
        
        if st.button("Set Alert", use_container_width=True, type="primary"):
            payload = {
                "phone_number": phone_number, "ticker": ticker,
                "target_price": target_price, "condition": condition_options[condition_label],
                "delete_on_trigger": delete_on_trigger
            }
            try:
                response = requests.post(f"{BACKEND_URL}/api/add_alert", json=payload)
                st.success("✅ Alert set successfully!")
            except requests.ConnectionError:
                st.error("Could not connect to the backend.")

with col2:
    st.header("🔔 Your Active Alerts")
    
    if st.button("🔄 Refresh Alerts", use_container_width=True):
        st.rerun()

    try:
        res = requests.get(f"{BACKEND_URL}/api/get_alerts/{phone_number}")
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