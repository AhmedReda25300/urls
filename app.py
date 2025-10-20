import streamlit as st
import json
from pathlib import Path
import threading

# --- Configuration & Data Persistence ---
# Define the path for the JSON file where endpoints are stored.
# Streamlit Cloud provides a persistent filesystem for your app.
DATA_FILE = Path("endpoints.json")
file_lock = threading.Lock()

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

# This is an advanced technique to access the raw HTTP request.
# It is necessary to differentiate between GET, POST, and a user visiting the UI.
http_request = None
try:
    from streamlit.web.server.server import Server
    from streamlit.runtime.scriptrunner import get_script_run_ctx
    
    ctx = get_script_run_ctx()
    server = Server.get_current()
    session_info = server._session_info_by_id.get(ctx.session_id)
    http_request = session_info.ws.request
except (ImportError, AttributeError):
    st.error("Could not access request details. POST requests may not work in this Streamlit version.")

# Check the query parameters to see if this is an API call
endpoint_name = st.query_params.get("endpoint", None)

# --- API Handling Mode ---
if endpoint_name and http_request:
    endpoints_data = load_endpoints()
    
    # --- HANDLE POST REQUEST (from a webhook) ---
    if http_request.method == "POST":
        if endpoint_name in endpoints_data:
            try:
                # Read the body of the POST request
                request_body = http_request.body.decode("utf-8")
                incoming_data = json.loads(request_body)
                
                # Update the existing data and save it
                endpoints_data[endpoint_name].update(incoming_data)
                save_endpoints(endpoints_data)
                
                st.json({"status": "success", "message": f"Endpoint '{endpoint_name}' updated."})
            except json.JSONDecodeError:
                st.error("Bad Request: Invalid JSON in POST body.")
                st.json({"error": "Bad Request", "status": 400})
        else:
            st.error(f"Endpoint '{endpoint_name}' not found.")
            st.json({"error": "Endpoint not found", "status": 404})
        # IMPORTANT: Stop the script after handling the API request
        st.stop()

    # --- HANDLE GET REQUEST ---
    elif http_request.method == "GET":
        if endpoint_name in endpoints_data:
            st.json(endpoints_data[endpoint_name])
        else:
            st.error(f"Endpoint '{endpoint_name}' not found.")
            st.json({"error": "Endpoint not found", "status": 404})
        # IMPORTANT: Stop the script after handling the API request
        st.stop()

# --- UI Management Mode ---
# This part only runs if the URL does not contain "?endpoint=..."
st.title("🚀 Deployed API & Webhook Manager")
st.markdown("Manage your endpoints below. Once deployed, use the generated URLs for your webhooks.")

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
            clean_name = new_endpoint_name.strip().lower().replace(' ', '_')
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

st.divider()

endpoints_data = load_endpoints()
if endpoints_data:
    st.subheader("📋 Your Live Endpoints")
    st.info("After deploying, replace 'localhost:8501' with your public Streamlit app URL.")
    
    cols = st.columns(2)
    for idx, (key, data) in enumerate(list(endpoints_data.items())):
        with cols[idx % 2]:
            with st.container(border=True):
                st.markdown(f"### {key}")
                
                # Construct the webhook URL
                # NOTE: Manually change this if your dev server isn't on 8501
                api_url = f"http://localhost:8501?endpoint={key}"
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
