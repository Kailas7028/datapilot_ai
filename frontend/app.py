import streamlit as st
import requests
import pandas as pd
import os
import time

# --- Configuration ---
# Ensure these match your FastAPI server routes!
BASE_URL = os.getenv("BACKEND_URL", "http://127.0.0.1:8000/api/v1")
API_URL = f"{BASE_URL}/query"
LOGIN_URL = f"{BASE_URL}/login"
REGISTER_URL = f"{BASE_URL}/register"

st.set_page_config(page_title="Datapilot AI Insights", page_icon="📊", layout="wide")

# --- UI Helper: Coming Soon Notification ---
def show_coming_soon(feature_name):
    """Displays a sleek popup for features currently in development."""
    st.toast(f"🚧 **{feature_name}** is currently in development. Coming soon!", icon="⏳")

# --- CSS Injection (Minimalist OLED Polish) ---
# --- ONE MASTER CSS INJECTION ---
st.markdown("""
    <style>
    /* 1. Global App Canvas */
    .stApp {
        background-color: #111111;
        color: #EDEDED;
    }

    /* 2. Sidebar Customization */
    [data-testid="stSidebar"] {
        background-color: #1A1A1A !important;
        
   

    /* 3. Input Boxes (The "Hollow" Modern Look) */
    div[data-baseweb="input"] {
        background-color: #1A1A1A !important;
        border: 1px solid #333333 !important;
        border-radius: 8px;
    }
    div[data-baseweb="input"]:focus-within {
        border-color: #0070F3 !important;
        box-shadow: 0 0 0 1px #0070F3 !important;
    }
    div[data-baseweb="input"] > div > input {
        color: #FFFFFF !important;
    }

  /* 4. Global Text-Based UI */
    /* This makes the "Home > Session" breadcrumb look professional */
    .stMarkdown p {
        font-size: 0.9rem;
        color: #555555; /* Dim gray */
    }

    /* 5. Primary/Action Buttons (Blue) */
    .stButton > button[data-testid="baseButton-primary"] {
        background-color: #0070F3 !important;
        color: #FFFFFF !important;
    }

    /* 6. Clean Text-Only Action Bar (Top Right) */
    [data-testid="column"] .stButton > button {
        background-color: transparent !important;
        border: none !important;
        color: #888888 !important; /* Muted gray for unselected words */
        font-size: 0.85rem !important;
        font-weight: 500 !important;
        text-transform: uppercase !important; /* Makes it look like a menu */
        letter-spacing: 1px !important;
        padding: 0px !important; /* Removes the "box" padding */
        box-shadow: none !important;
    }

    /* Elegant Hover: The word glows blue and lifts slightly */
    [data-testid="column"] .stButton > button:hover {
        color: #0070F3 !important; /* Electric Blue glow */
        background-color: transparent !important;
        transform: translateY(-1px);
    }

    /* 7. Sample Questions (Mint/Green Hierarchy) */
    .stExpander {
        background-color: #1A1A1A !important;
        border: 1px solid #285A48 !important;
        border-radius: 8px !important;
    }
    .stExpander .stButton > button {
        background-color: #091413 !important; /* Deep Forest */
        border: 1px solid #285A48 !important;
        color: #B0E4CC !important; /* Mint Text */
        text-align: left !important;
    }
    .stExpander .stButton > button:hover {
        background-color: #285A48 !important;
        color: #FFFFFF !important;
        transform: translateX(5px) !important; /* Pro UI Slide Effect */
    }

    /* 8. Tabs (Login & Dashboard) */
    .stTabs [data-baseweb="tab"] { color: #888888; }
    .stTabs [aria-selected="true"] {
        color: #EDEDED !important;
        border-bottom: 2px solid #0070F3 !important;
    }
 
    </style>
""", unsafe_allow_html=True)

# --- Session State Initialization ---
if "access_token" not in st.session_state:
    st.session_state.access_token = None
if "messages" not in st.session_state:
    st.session_state.messages = []

# ==========================================
# 🔒 THE DRIBBBLE-STYLE LOGIN PAGE
# ==========================================
if not st.session_state.access_token:
    st.write("<br><br><br>", unsafe_allow_html=True)
    
    left_brand, spacer, right_form = st.columns([1.2, 0.2, 1])
    
    with left_brand:
        st.markdown("<h1 style='font-size: 3.5rem; color: #ffffff;'>Datapilot AI<br>Insights.</h1>", unsafe_allow_html=True)
        st.markdown("<p style='font-size: 1.2rem; color: #a0a0a0;'>Unlock the power of your data with conversational AI.<br>Secure, fast, and intelligent.</p>", unsafe_allow_html=True)
        
        if st.button("Read the Documentation", key="doc_btn"):
            show_coming_soon("Documentation Portal")

    with right_form:
        with st.container():
            st.markdown("### Welcome Back")
            tab_login, tab_register = st.tabs(["Log In", "Create Account"])
            
            with tab_login:
                with st.form("login_form"):
                    username = st.text_input("Email Address", placeholder="name@company.com")
                    password = st.text_input("Password", type="password", placeholder="••••••••")

                    if st.form_submit_button("Sign In", type="primary", use_container_width=True):
                        with st.status("Connecting to server...",expanded=True) as status:
                            st.write("This may take a moment if the server is waking up from sleep.")
                            server_awake = False
                            browser_header = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"}
                            for i in range(15):
                                try:
                                    pulse = requests.get("https://datapilot-ai-cug8.onrender.com/", headers=browser_header, timeout=10)
                                    if pulse.status_code not in [502,503]:
                                        server_awake = True
                                        break
                                except requests.exceptions.RequestException:
                                    pass
                                status.update(label=f"Cloud server is waking up... ({i+1}/15) attempts",state="running")
                                time.sleep(5)
                            if not server_awake:
                                status.update(label="Server waking-up timed out.", state="error")
                                st.error("Login failed due to server timeout. The server may be waking up from sleep. Please wait a moment and try again.")
                            else:
                                status.update(label="Server is awake! Attempting to log in...", state="running")
                                st.write("Sending login request...")
                            
                                try:
                                    response = requests.post(LOGIN_URL, data={"username": username, "password": password}, timeout=60, headers=browser_header)
                                    if response.status_code in [502,503]:
                                        st.warning("The cloud server is currently waking up from sleep. Please wait 1 minute and click Login again!")
                                    elif response.status_code == 200:
                                        st.success("Login successful!")
                                        st.session_state.access_token = response.json().get("access_token")
                                        st.rerun()
                                    else:
                                        error_details = response.json().get("detail", "Login failed.")
                                        st.error(error_details)
                                except requests.exceptions.ReadTimeout:
                                    st.error("Login timed out. The server may be waking up from sleep. Please wait a moment and try again.")
                                except requests.exceptions.JSONDecodeError:
                                    st.error(f"Server Error. Raw Response: {response.text[:100]}")
                                except requests.exceptions.ConnectionError:
                                    st.error("Could not connect to the backend server. Is your server running?")
                            
            with tab_register:
                with st.form("register_form"):
                    new_username = st.text_input("Email Address")
                    new_password = st.text_input("Password", type="password")
                    if st.form_submit_button("Sign Up", type="primary", use_container_width=True):
                        with st.status("Creating your account...",expanded=True) as status:
                            st.write("This may take a moment if the server is waking up from sleep.")
                            server_awake = False
                            for i in range(15):
                                try:
                                    pulse = requests.get("https://datapilot-ai-cug8.onrender.com/",timeout=5)
                                    if pulse.status_code == 200:
                                        server_awake = True
                                        break
                                except requests.exceptions.RequestException:
                                    pass
                                status.update(label=f"Cloud server is waking up... ({i+1}/15) attempts",state="running")
                                time.sleep(5)
                            if not server_awake:
                                status.update(label="Server waking-up timed out.", state="error")
                                st.error("Registration failed due to server timeout. The server may be waking up from sleep. Please wait a moment and try again.")
                            else:
                                status.update(label="Server is awake! Attempting to register...", state="running")
                                st.write("Sending registration request...")
                                try:
                                    response = requests.post(REGISTER_URL, json={"username": new_username, "password": new_password},timeout=60)
                                    if response.status_code == 201:
                                        st.success("Account created successfully! You can now log in.")
                                    elif response.status_code in [502,503]:
                                            st.warning("The cloud server is currently waking up from sleep. Please wait 1 minute and click Sign Up again!")
                                    else:
                                        st.error(response.json().get("detail", "Registration failed."))
                                except requests.exceptions.ReadTimeout:
                                    st.error("Registration timed out. The server may be waking up from sleep. Please wait a moment and try again.")
                                except requests.exceptions.ConnectionError:
                                    st.error("Could not connect to the backend server. Is your server running?")
                                except requests.exceptions.JSONDecodeError:
                                    st.error(f"Server Error. Raw Response: {response.text[:100]}")

# ==========================================
# 📊 MAIN DASHBOARD (Logged In)
# ==========================================
else:
    with st.sidebar:
        st.markdown("### Menu")
        st.button("Home", width="stretch")
        
        if st.button("Configurations", width="stretch"):
            show_coming_soon("User Configurations")
            
        st.markdown("---")
        
        # ==========================================
        # 🔍 DATA INSIGHTS SECTION
        # ==========================================
        st.markdown("### Data Insights")
        
        # 1. Data Health Indicators
        st.caption("🟢 **Status:** Connected to 'airbnb_india_db'")
        st.caption("📊 **Total Records:** 25 rows synced")
        
        st.write("") # Small spacer
        
        # 2. Table Schema Explorer
        st.markdown("**Schema Explorer**")
        
        with st.expander("📂 hosts (5 rows)"):
            st.markdown("""
            - `id` *(integer)*
            - `host_name` *(varchar)*
            - `host_since` *(date)*
            - `host_location` *(varchar)*
            - `is_superhost` *(boolean)*
            """)
            
        with st.expander("📂 listings (8 rows)"):
            st.markdown("""
            - `id` *(integer)*
            - `name` *(text)*
            - `host_id` *(integer, FK)*
            - `neighbourhood` *(varchar)*
            - `property_type` *(varchar)*
            - `room_type` *(varchar)*
            - `accommodates` *(integer)*
            - `price_per_night` *(numeric)*
            - `average_rating` *(numeric)*
            """)
            
        with st.expander("📂 reviews (12 rows)"):
            st.markdown("""
            - `id` *(integer)*
            - `listing_id` *(integer, FK)*
            - `review_date` *(date)*
            - `comments` *(text)*
            """)

        st.markdown("---")

        st.write("<br><br>", unsafe_allow_html=True) # Push logout to bottom
        if st.button("Logout", width="stretch"):
            st.session_state.access_token = None
            st.session_state.messages = []
            st.rerun()
    # --- Top Action Bar ---
 # --- Top Action Bar (Right Aligned) ---
# [4, 1, 1, 1] means the first column takes 4x more space, pushing others right
    spacer, col_share, col_exit, col_delete = st.columns([4, 0.5, 0.5, 0.5])

    with col_share:
        if st.button("Share"): 
            show_coming_soon("Session Sharing")

    with col_exit:
        if st.button("Exit"): 
            show_coming_soon("Exit Session")

    with col_delete:
        if st.button("Delete"): 
            st.session_state.messages = []
            st.rerun()

    st.markdown("<hr style='margin-top: 0; border: 0.5px solid #222;'>", unsafe_allow_html=True)
    # --- Main Chat Interface ---
    st.markdown("## Datspilot AI Insights")
    st.write("Welcome to your secure workspace. Start typing below to query your database.")

    # --- Render Sample Questions (Only if chat is empty) ---
    if not st.session_state.messages:
        with st.expander("💡 Here are some sample questions", expanded=True):
            if st.button("Superhosts in Delhi", width="stretch"):
                st.toast("Copy and paste this into the chat below!", icon="💡")
            if st.button("Average price of Villas vs Apartments", width="stretch"):
                st.toast("Copy and paste this into the chat below!", icon="💡")

    # --- Render Chat History ---
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            if msg["role"] == "user":
                st.write(msg["content"])
            else:
                tabs = st.tabs(["Insights", "Data", "Code", "Visualizations", "Lineage"])
                with tabs[0]: st.write(msg.get("insight", "Query executed successfully."))
                with tabs[1]: st.dataframe(msg.get("data", []), width="stretch")
                with tabs[2]: st.code(msg.get("sql", "-- No SQL provided"), language="sql")
                with tabs[3]: st.info("Visualization engine coming soon.")
                with tabs[4]: st.caption("Data Lineage tracking not enabled.")

    # --- User Input Bar ---
    prompt = st.chat_input("Type your question here or type an SQL query to run...")

    if prompt:
        # 1. Display User Message instantly
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.write(prompt)

        # 2. Call the FastAPI Backend
        with st.chat_message("assistant"):
            with st.spinner("Analyzing database schema and generating insights..."):
                try:
                    headers = {"Authorization": f"Bearer {st.session_state.access_token}"}
                    response = requests.post(API_URL, json={"question": prompt}, headers=headers)
                    
                    if response.status_code == 200:
                        api_data = response.json()
                        generated_sql = api_data.get("generated_sql", "-- SQL not found")
                        sql_results = api_data.get("result", [])
                        insight_text = api_data.get("result_summary", "No insights generated.")
                        # ---> ADD THIS LINE <---
                        insight_text = insight_text.replace("$", r"\$")
                        
                        # Display response in tabs
                        tabs = st.tabs(["Insights", "Data", "Code", "Visualizations", "Lineage"])
                        with tabs[0]: st.write(insight_text)
                        with tabs[1]: st.dataframe(sql_results, width="stretch")
                        with tabs[2]: st.code(generated_sql, language="sql")
                        with tabs[3]: st.info("Visualization engine coming soon.")
                        with tabs[4]: st.caption("Data Lineage tracking not enabled.")
                        
                        # Save to chat history
                        st.session_state.messages.append({
                            "role": "assistant",
                            "insight": insight_text,
                            "data": sql_results,
                            "sql": generated_sql
                        })
                        
                    elif response.status_code == 401:
                        st.error("Session expired. Please log in again.")
                        st.session_state.access_token = None
                        st.rerun()
                    else:
                        st.error(f"API Error {response.status_code}: {response.text}")
                
                except requests.exceptions.ConnectionError:
                    st.error("🚨 Could not connect to the backend API. Is your FastAPI server running on port 8000?")