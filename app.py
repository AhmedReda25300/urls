import streamlit as st
import json
from pathlib import Path
import threading
import os

# --- Configuration & Data Persistence ---
DATA_FILE = Path("endpoints.json")
file_lock = threading.Lock()  # Use a lock for file access safety

def load_endpoints():
    """Loads the endpoints dictionary from the JSON file safely."""
    with file_lock:
        if DATA_FILE.exists():
            try:
                with open(DATA_FILE, "r") as f:
                    return json.load(f)
            except (json.JSONDecodeError, ValueError):
                return {}
    return {}

def save_endpoints(endpoints_dict):
    """Saves the endpoints dictionary to the JSON file safely."""
    with file_lock:
        with open(DATA_FILE, "w") as f:
            json.dump(endpoints_dict, f, indent=2)

# --- Main Application Logic ---
st.set_page_config(page_title="API Endpoint Manager", layout="wide")

# Get the base URL dynamically for deployment
# In Streamlit Cloud, the app's public URL can be approximated or set manually
# For local testing, use localhost; for deployment, use the deployed URL
BASE_URL = os.getenv("STREAMLIT_URL", "http://localhost:8501")  # Set STREAMLIT_URL in Streamlit Cloud environment variables

# Check query parameters to determine if this is an API call
endpoint_name = st.query_params.get("endpoint", None)

# --- API Handling Mode ---
if endpoint_name:
    endpoints_data = load_endpoints()
    
    # Handle POST-like requests via a hidden form (for webhook-like updates)
    if "post_data" in st.session_state and endpoint_name in endpoints_data:
        try:
            incoming_data = json.loads(st.session_state.post_data)
            endpoints_data[endpoint_name].update(incoming_data)
            save_endpoints(endpoints_data)
            st.json({"status": "success", "message": f"Endpoint '{endpoint_name}' updated."})
            del st.session_state.post_data  # Clear session state
            st.stop()
        except json.JSONDecodeError:
            st.json({"error": "Bad Request: Invalid JSON in POST body.", "status": 400})
            st.stop()

    # Handle GET requests
    if endpoint_name in endpoints_data:
        st.json(endpoints_data[endpoint_name])
    else:
        st.json({"error": "Endpoint not found", "status": 404})
    st.stop()

# --- UI Management Mode (Default View) ---
st.title("🚀 Deployed API & Webhook Manager")
st.markdown("Manage your endpoints below. Once deployed, use the generated URLs for your webhooks.")

# Form for creating or updating endpoints
with st.form(key="create_endpoint_form"):
    st.subheader("Create or Update an Endpoint")
    col1, col2 = st.columns([1, 2])
    with col1:
        new_endpoint_name = st.text_input("Endpoint Name", placeholder="e.g., userinfo")
    with col2:
        json_data_str = st.text_area("Initial JSON Data", height=150, placeholder='{\n  "status": "pending"\n}')
    
    submit_button = st.form_submit_button(label="💾 Save Endpoint", use_container_width=True)

    if submit_button:
        if new_endpoint_name and json_data_str:
            clean_name = new_endpoint_name.strip().lower().replace(" ", "_")
            try:
                endpoints_data = load_endpoints()
                endpoints_data[clean_name] = json.loads(json_data_str)
                save_endpoints(endpoints_data)
                st.success(f"Endpoint '{clean_name}' saved successfully!")
                st.rerun()
            except json.JSONDecodeError:
                st.error("Invalid JSON format. Please check your data.")
        else:
            st.warning("Please provide both an endpoint name and JSON data.")

# Form for simulating POST requests (for testing in the UI)
with st.form(key="post_endpoint_form"):
    st.subheader("Test POST to Endpoint")
    col1, col2 = st.columns([1, 2])
    with col1:
        post_endpoint_name = st.text_input("Endpoint to Update", placeholder="e.g., userinfo")
    with col2:
        post_json_data = st.text_area("JSON Data to POST", height=150, placeholder='{\n  "status": "updated"\n}')
    
    post_submit_button = st.form_submit_button(label="📤 Send POST", use_container_width=True)

    if post_submit_button:
        if post_endpoint_name and post_json_data:
            endpoints_data = load_endpoints()
            clean_post_name = post_endpoint_name.strip().lower().replace(" ", "_")
            if clean_post_name in endpoints_data:
                try:
                    st.session_state.post_data = post_json_data  # Store POST data in session state
                    st.query_params["endpoint"] = clean_post_name  # Simulate API call
                    st.rerun()
                except json.JSONDecodeError:
                    st.error("Invalid JSON format in POST data.")
            else:
                st.error(f"Endpoint '{clean_post_name}' not found.")
        else:
            st.warning("Please provide both an endpoint name and JSON data.")

st.divider()

# Display existing endpoints
endpoints_data = load_endpoints()
if endpoints_data:
    st.subheader("📋 Your Live Endpoints")
    st.info(f"After deploying, your public URLs will look like: {BASE_URL}?endpoint=...")
    
    cols = st.columns(2)
    for idx, (key, data) in enumerate(endpoints_data.items()):
        with cols[idx % 2]:
            with st.container(border=True):
                st.markdown(f"### {key}")
                
                api_url = f"{BASE_URL}?endpoint={key}"
                st.markdown("**Webhook URL:**")
                st.code(api_url, language="text")

                with st.expander("View Current JSON"):
                    st.json(data)

                if st.button("🗑️ Delete", key=f"del_{key}", use_container_width=True, type="secondary"):
                    del endpoints_data[key]
                    save_endpoints(endpoints_data)
                    st.rerun()
else:
    st.info("Create your first endpoint using the form above.")
