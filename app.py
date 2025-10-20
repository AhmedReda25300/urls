
import streamlit as st
import json
from pathlib import Path
import threading
import os

# --- Configuration & Data Persistence ---
# Use a lock for thread-safe file access, good practice though Streamlit runs scripts linearly.
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
                # Return an empty dict if the file is corrupted or empty
                return {}
    return {}

def save_endpoints(endpoints_dict):
    """Saves the endpoints dictionary to the JSON file safely."""
    with file_lock:
        with open(DATA_FILE, "w") as f:
            json.dump(endpoints_dict, f, indent=2)

# --- Main Application Logic ---
st.set_page_config(page_title="API Endpoint Manager", layout="wide")

# --- FIX: Dynamic Base URL for Deployment ---
# The original code defaults to localhost. This fix prioritizes a user-set environment variable,
# which is necessary for deployed apps on Streamlit Community Cloud.
# The user must set the 'STREAMLIT_URL' secret in their app's settings.
BASE_URL = os.getenv("STREAMLIT_URL", "http://localhost:8501")
IS_DEPLOYED = "streamlit.app" in BASE_URL

# Check query parameters to determine if this is an API call (for GET requests)
endpoint_name = st.query_params.get("endpoint", None)

# --- API Handling Mode (Handles GET requests from external services) ---
if endpoint_name:
    endpoints_data = load_endpoints()
    
    # This section handles a simulated POST from the UI by using session_state and rerun.
    # NOTE: This does NOT handle true external POST requests.
    if "post_data" in st.session_state and endpoint_name in endpoints_data:
        try:
            incoming_data = json.loads(st.session_state.post_data)
            endpoints_data[endpoint_name].update(incoming_data)
            save_endpoints(endpoints_data)
            st.json({"status": "success", "message": f"Endpoint '{endpoint_name}' updated."})
            del st.session_state.post_data  # Clean up session state
        except json.JSONDecodeError:
            st.status_code = 400
            st.json({"error": "Bad Request: Invalid JSON format."})
        finally:
            # Stop the script execution after handling the API request.
            st.stop()

    # Handle standard GET requests
    if endpoint_name in endpoints_data:
        st.json(endpoints_data[endpoint_name])
    else:
        st.status_code = 404
        st.json({"error": "Endpoint not found"})
    st.stop()

# --- UI Management Mode (Default View) ---
st.title("🚀 Live JSON Endpoint Manager")
st.markdown("Create, manage, and view simple JSON endpoints. These endpoints are publicly readable (GET requests).")

# Display a warning if the app is likely deployed but the public URL is not configured
if BASE_URL == "http://localhost:8501":
    # A simple check to infer if it's running on Streamlit Cloud without the secret set.
    # This is a heuristic and might not cover all cases.
    st.warning(
        """
        **⚠️ Configuration Needed for Deployed App**
        
        It looks like this app might be deployed. To ensure the Webhook URLs are correct, 
        please go to your app's **Settings > Secrets** and add a secret:
        
        `STREAMLIT_URL="your_app_url"`
        
        Replace `your_app_url` with the actual URL from your browser's address bar.
        """,
        icon="⚙️"
    )


# Form for creating or updating endpoints
with st.form(key="create_endpoint_form"):
    st.subheader("Create or Update an Endpoint")
    col1, col2 = st.columns([1, 2])
    with col1:
        new_endpoint_name = st.text_input("Endpoint Name", placeholder="e.g., userinfo")
    with col2:
        json_data_str = st.text_area("Initial JSON Data", height=150, placeholder='{\n  "name": "ahmed",\n  "status": "pending"\n}')
    
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

# Clarification about POST functionality
st.subheader("Test Endpoint Updates (POST Simulation)")
st.info("This form simulates updating an endpoint's JSON data. Note: The endpoints do not accept true `POST` requests from external services; this is for testing via the UI only.", icon="ℹ️")

# Form for simulating POST requests
with st.form(key="post_endpoint_form"):
    col1, col2 = st.columns([1, 2])
    with col1:
        post_endpoint_name = st.text_input("Endpoint to Update", placeholder="e.g., userinfo")
    with col2:
        post_json_data = st.text_area("JSON Data to Update With", height=150, placeholder='{\n  "status": "completed"\n}')
    
    post_submit_button = st.form_submit_button(label="📤 Send Update", use_container_width=True)

    if post_submit_button:
        if post_endpoint_name and post_json_data:
            endpoints_data = load_endpoints()
            clean_post_name = post_endpoint_name.strip().lower().replace(" ", "_")
            if clean_post_name in endpoints_data:
                try:
                    # Validate JSON before attempting the update
                    json.loads(post_json_data)
                    st.session_state.post_data = post_json_data
                    # Use query_params to trigger the API handling logic on rerun
                    st.query_params["endpoint"] = clean_post_name
                    st.rerun()
                except json.JSONDecodeError:
                    st.error("Invalid JSON format in the update data.")
            else:
                st.error(f"Endpoint '{clean_post_name}' not found.")
        else:
            st.warning("Please provide both an endpoint name and the JSON data for the update.")

st.divider()

# Display existing endpoints
endpoints_data = load_endpoints()
if endpoints_data:
    st.subheader("📋 Your Live Endpoints")
    st.info(f"Your public base URL is: `{BASE_URL}`")
    
    # Create a responsive grid
    num_columns = 2
    cols = st.columns(num_columns)
    
    for idx, (key, data) in enumerate(endpoints_data.items()):
        with cols[idx % num_columns]:
            with st.container(border=True):
                st.markdown(f"### {key}")
                
                api_url = f"{BASE_URL}?endpoint={key}"
                st.markdown("**Webhook URL (GET):**")
                st.code(api_url, language="text")

                with st.expander("View Current JSON"):
                    st.json(data)

                if st.button("🗑️ Delete", key=f"del_{key}", use_container_width=True, type="secondary"):
                    endpoints = load_endpoints()
                    if key in endpoints:
                        del endpoints[key]
                        save_endpoints(endpoints)
                        st.rerun()
else:
    st.info("You haven't created any endpoints yet. Use the form above to get started.")
