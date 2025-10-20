import streamlit as st
import json
from pathlib import Path
import threading
import http.server
import socketserver
from urllib.parse import urlparse

# --- Configuration ---
# Port for the Streamlit UI
STREAMLIT_PORT = 8501
# Port for the API (for GET/POST requests and webhooks)
API_PORT = 8000
# Define the path for the JSON file where endpoints are stored
DATA_FILE = Path("endpoints.json")

# --- Data Persistence Logic ---
# A thread lock to prevent race conditions when reading/writing the file
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

# --- API Server for GET/POST Webhooks ---

class WebhookHandler(http.server.SimpleHTTPRequestHandler):
    """Custom request handler for our API."""
    
    def do_GET(self):
        """Handles GET requests to fetch endpoint data."""
        parsed_path = urlparse(self.path)
        endpoint_name = parsed_path.path.strip('/')
        
        endpoints_data = load_endpoints()
        
        if endpoint_name in endpoints_data:
            self.send_response(200)
            self.send_header("Content-type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(endpoints_data[endpoint_name], indent=2).encode('utf-8'))
        else:
            self.send_response(404)
            self.send_header("Content-type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"error": "Endpoint not found"}).encode('utf-8'))

    def do_POST(self):
        """Handles POST requests to update or add data to an endpoint."""
        parsed_path = urlparse(self.path)
        endpoint_name = parsed_path.path.strip('/')
        
        endpoints_data = load_endpoints()
        
        if endpoint_name in endpoints_data:
            try:
                content_length = int(self.headers['Content-Length'])
                post_data_bytes = self.rfile.read(content_length)
                incoming_data = json.loads(post_data_bytes)
                
                # Update the existing endpoint data with the new data
                endpoints_data[endpoint_name].update(incoming_data)
                save_endpoints(endpoints_data)
                
                self.send_response(200)
                self.send_header("Content-type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"status": "success", "message": "Endpoint updated"}).encode('utf-8'))
            except (json.JSONDecodeError, KeyError):
                self.send_response(400)
                self.send_header("Content-type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"error": "Bad request. Invalid JSON or missing headers."}).encode('utf-8'))
        else:
            self.send_response(404)
            self.send_header("Content-type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"error": "Endpoint not found"}).encode('utf-8'))

def run_api_server():
    """Starts the API server in a background thread."""
    with socketserver.TCPServer(("", API_PORT), WebhookHandler) as httpd:
        print(f"API server started on port {API_PORT}")
        httpd.serve_forever()

# Start the server only once using session state as a flag
if 'api_server_started' not in st.session_state:
    thread = threading.Thread(target=run_api_server, daemon=True)
    thread.start()
    st.session_state.api_server_started = True

# --- Streamlit UI ---

st.set_page_config(page_title="API Endpoint Manager", layout="wide")
st.title("🌐 API & Webhook Manager")
st.markdown(f"Manage your endpoints below. Your API is live and listening for **GET** and **POST** requests on `http://localhost:{API_PORT}`.")

with st.form(key="create_endpoint_form"):
    st.subheader("Create or Update an Endpoint")
    col1, col2 = st.columns([1, 2])
    with col1:
        new_endpoint_name = st.text_input("Endpoint Name", placeholder="e.g., userinfo")
    with col2:
        json_data_str = st.text_area("JSON Data", height=150, placeholder='{\n  "name": "Default Name",\n  "status": "pending"\n}')
    
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

# Display existing endpoints
endpoints_data = load_endpoints()
if endpoints_data:
    st.subheader("📋 Your Live Endpoints")
    base_url = f"http://localhost:{API_PORT}"
    
    cols = st.columns(2)
    endpoints_items = list(endpoints_data.items())

    for idx, (endpoint_key, endpoint_data) in enumerate(endpoints_items):
        with cols[idx % 2]:
            with st.container(border=True):
                st.markdown(f"### {endpoint_key}")
                
                api_url = f"{base_url}/{endpoint_key}"
                st.markdown("**API URL:**")
                st.code(api_url, language="text")

                with st.expander("View Current JSON"):
                    st.json(endpoint_data)

                if st.button("🗑️ Delete", key=f"del_{endpoint_key}", use_container_width=True, type="secondary"):
                    del endpoints_data[endpoint_key]
                    save_endpoints(endpoints_data)
                    st.rerun()
else:
    st.info("You haven't created any endpoints yet. Use the form above to get started.")
