import streamlit as st
import requests
import pandas as pd

# --- Configuration ---
# Ensure these match your FastAPI server routes!
BASE_URL = "http://127.0.0.1:8000/api/v1"
API_URL = f"{BASE_URL}/query"
LOGIN_URL = f"{BASE_URL}/login"
REGISTER_URL = f"{BASE_URL}/register"

st.set_page_config(page_title="Marketing Data Insights", page_icon="📊", layout="wide")

# --- Custom CSS to match Enterprise Dashboard ---
st.markdown("""
    <style>
    .stButton button { border-radius: 20px; }
    .stTabs [data-baseweb="tab-list"] { gap: 24px; }
    .stTabs [data-baseweb="tab"] { height: 50px; white-space: pre-wrap; padding-top: 10px; padding-bottom: 10px; }
    </style>
""", unsafe_allow_html=True)

# --- Session State Initialization ---
if "access_token" not in st.session_state:
    st.session_state.access_token = None
if "messages" not in st.session_state:
    st.session_state.messages = []

# ==========================================
# 🔒 AUTHENTICATION SCREEN (Not Logged In)
# ==========================================
if not st.session_state.access_token:
    st.title("Welcome to AURA Insights")
    st.markdown("Please log in or create an account to access your database.")
    
    tab_login, tab_register = st.tabs(["Login", "Sign Up"])
    
    with tab_login:
        with st.form("login_form"):
            username = st.text_input("Email Address")
            password = st.text_input("Password", type="password")
            if st.form_submit_button("Login"):
                # FastAPI OAuth2 expects form data, not JSON
                response = requests.post(LOGIN_URL, data={"username": username, "password": password})
                if response.status_code == 200:
                    st.session_state.access_token = response.json().get("access_token")
                    st.rerun()
                else:
                    st.error("Invalid email or password.")
                    
    with tab_register:
        with st.form("register_form"):
            new_username = st.text_input("Email Address")
            new_password = st.text_input("Choose a Password", type="password")
            if st.form_submit_button("Create Account"):
                response = requests.post(REGISTER_URL, json={"username": new_username, "password": new_password})
                if response.status_code == 201:
                    st.success("Account created successfully! You can now log in.")
                else:
                    st.error(response.json().get("detail", "Registration failed."))

# ==========================================
# 📊 MAIN DASHBOARD (Logged In)
# ==========================================
else:
    # --- Sidebar (Navigation) ---
    with st.sidebar:
        st.markdown("### Menu")
        st.button("Home", width="stretch")
        st.button("Database Insights", width="stretch")
        st.button("Sample Questions", width="stretch")
        st.button("Configurations", width="stretch")
        st.markdown("---")
        st.caption("Current Configuration - gpt-35-turbo, 2000 rows")
        
        # Logout button
        if st.button("Logout", width="stretch"):
            st.session_state.access_token = None
            st.session_state.messages = []
            st.rerun()

    # --- Top Action Bar ---
    col1, col2, col3, col4, col5 = st.columns([2, 1, 1, 1, 1])
    with col1: st.write("**Home > Save Session**")
    with col2: st.button("🔗 Share Session")
    with col3: st.button("🚪 Exit Session")
    with col4: st.button("🗑️ Delete Session")
    st.markdown("---")

    # --- Main Chat Interface ---
    st.write("👋 **Welcome to AURA.** You are connected to Marketing Data Insights.")
    st.write("Please start by asking a question on your database.")

    # --- Render Sample Questions (Only if chat is empty) ---
    if not st.session_state.messages:
        with st.expander("💡 Here are some sample questions", expanded=True):
            st.button("Show customer id, income, marital status... for customers with income greater than $30,000.", width="stretch")
            st.button("What is the total amount of all paid invoices for annual subscriptions?", width="stretch")
            st.button("How many customers have high probability of acceptance for next campaign offer?", width="stretch")

    # --- Render Chat History ---
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            if msg["role"] == "user":
                st.write(msg["content"])
            else:
                tabs = st.tabs(["Insights", "Data", "Code", "Visualizations", "Lineage"])
                with tabs[0]: st.write(msg.get("insight", "Query executed successfully."))
                with tabs[1]: st.dataframe(msg.get("data", []), width="stretch")
                with tabs[2]: st.code(msg.get("sql", "No SQL provided"), language="sql")
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
                    # CRITICAL: Attach JWT Token to headers
                    headers = {"Authorization": f"Bearer {st.session_state.access_token}"}
                    
                    # Send HTTP POST request to FastAPI server
                    response = requests.post(API_URL, json={"question": prompt}, headers=headers)
                    
                    if response.status_code == 200:
                        api_data = response.json()
                        
                        # Extract data from API response
                        generated_sql = api_data.get("generated_sql", "-- SQL not found")
                        sql_results = api_data.get("result", [])
                        insight_text = f"Successfully generated a {len(sql_results)} row report from your database."
                        
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