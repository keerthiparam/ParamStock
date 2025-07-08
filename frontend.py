import streamlit as st
import requests
import re # For phone number validation

# Backend API URL (this will be your deployment URL later)
BACKEND_URL = "http://127.0.0.1:5000"

st.title("📈 WhatsApp Stock Alerter")
st.write("Set a target price for an NSE stock and get a WhatsApp alert!")

# --- User Input Form ---
with st.form("alert_form", clear_on_submit=True):
    st.subheader("Create a New Alert")
    phone_number = st.text_input("Your WhatsApp Number (e.g., +919876543210)")
    ticker = st.text_input("Stock Ticker (e.g., RELIANCE, SBIN)").upper()
    condition = st.selectbox("Condition", ["above", "below"])
    target_price = st.number_input("Target Price (in INR)", min_value=0.01, format="%.2f")
    
    submitted = st.form_submit_button("Set Alert")

    if submitted:
        # Basic validation
        if not re.match(r"^\+91[6-9]\d{9}$", phone_number):
            st.error("Please enter a valid Indian WhatsApp number (e.g., +919876543210)")
        elif not ticker:
            st.error("Ticker cannot be empty.")
        else:
            # Send data to the backend API
            payload = {
                "phone_number": phone_number,
                "ticker": ticker,
                "target_price": target_price,
                "condition": condition
            }
            try:
                response = requests.post(f"{BACKEND_URL}/api/add_alert", json=payload)
                if response.status_code == 201:
                    st.success(f"✅ Alert for {ticker} set successfully!")
                else:
                    st.error(f"Error: {response.json().get('error', 'Unknown error')}")
            except requests.exceptions.ConnectionError:
                st.error("Could not connect to the backend server. Is it running?")

st.write("---")
st.subheader("Check Your Active Alerts")
check_phone = st.text_input("Enter your WhatsApp number to see your alerts")
if st.button("Fetch Alerts"):
    # Fetch and display existing alerts for the user
    res = requests.get(f"{BACKEND_URL}/api/get_alerts/{check_phone}")
    if res.status_code == 200:
        alerts = res.json()
        if alerts:
            for alert in alerts:
                status = "🔔 Triggered" if alert['alert_sent'] else "Active"
                st.info(f"**{alert['ticker']}**: Target is *{alert['condition']} ₹{alert['target_price']}*  |  **Status**: {status}")
        else:
            st.warning("No alerts found for this number.")