# frontend.py
import streamlit as st
import requests
import re

# --- Configuration ---
BACKEND_URL = "http://127.0.0.1:5000"

st.set_page_config(page_title="ParamStock Alerter", layout="wide")
st.title("📈 Smart Stock Alerter")

st.sidebar.header("Your Settings")
phone_number = st.sidebar.text_input("Enter Your WhatsApp Number to Begin (e.g., +91...)", key="phone_number")

if not phone_number or not re.match(r"^\+91[6-9]\d{9}$", phone_number):
    st.warning("Please enter a valid WhatsApp number in the sidebar to load or create alerts.")
    st.stop()

st.sidebar.success(f"Viewing alerts for: {phone_number}")

col1, col2 = st.columns(2)

with col1:
    st.header("Set a New Alert")
    condition_options = {
        'Price is >= (Above or Equal)': 'gte', 'Price is <= (Below or Equal)': 'lte',
        'Price is > (Strictly Above)': 'gt', 'Price is < (Strictly Below)': 'lt',
    }
    ticker = st.text_input("Stock Ticker (e.g., RELIANCE.NS, SBIN.NS, AAPL)").upper()
    condition_label = st.selectbox("Condition", options=list(condition_options.keys()))
    target_price = st.number_input("Target Price", min_value=0.01, format="%.2f")
    delete_on_trigger = st.checkbox("One-time alert (deletes itself after triggering)")
    
    if st.button("Set Alert", use_container_width=True):
        if not ticker:
            st.error("Ticker cannot be empty.")
        else:
            payload = {
                "phone_number": phone_number, "ticker": ticker,
                "target_price": target_price, "condition": condition_options[condition_label],
                "delete_on_trigger": delete_on_trigger
            }
            try:
                response = requests.post(f"{BACKEND_URL}/api/add_alert", json=payload)
                if response.status_code == 201:
                    st.success(f"✅ Alert for {ticker} set successfully!")
                else:
                    st.error(f"Error: {response.text}")
            except requests.ConnectionError:
                st.error("Could not connect to the backend. Is it running?")

with col2:
    st.header("Your Active Alerts")
    
    if st.button("Refresh Alerts", use_container_width=True):
        st.rerun()

    try:
        res = requests.get(f"{BACKEND_URL}/api/get_alerts/{phone_number}")
        if res.status_code == 200:
            alerts = res.json()
            if not alerts:
                st.info("No active alerts found for this number.")
            
            for alert in alerts:
                cond_map = {'gte': '>=', 'lte': '<=', 'gt': '>', 'lt': '<'}
                status = "🔔 TRIGGERED" if alert['alert_sent'] else "Active"
                
                alert_col, button_col = st.columns([4, 1])
                with alert_col:
                    st.markdown(f"**{alert['ticker']}** `{status}`\n\nTarget: Price {cond_map.get(alert['condition'], '?')} **₹{alert['target_price']:.2f}**")
                with button_col:
                    if st.button("Delete", key=f"del_{alert['id']}", use_container_width=True):
                        del_res = requests.post(f"{BACKEND_URL}/api/delete_alert/{alert['id']}")
                        if del_res.status_code == 200:
                            st.success("Deleted!")
                            st.rerun()
                        else:
                            st.error("Failed to delete.")
                st.markdown("---")
    except requests.ConnectionError:
        st.error("Could not connect to the backend server. Is it running?")