import streamlit as st
import requests
import pandas as pd
import os
import time
import uuid
import pandas as pd
import plotly.express as px

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# --- Configuration ---
# Ensure these match your FastAPI server routes!
BASE_URL = os.getenv("BACKEND_URL")
API_URL = f"{BASE_URL}/query"
LOGIN_URL = f"{BASE_URL}/login"
REGISTER_URL = f"{BASE_URL}/register"



st.set_page_config(page_title="Datapilot AI Insights", page_icon="page_icon.png", layout="wide")
#set background image
# --- UI Helper: Coming Soon Notification ---
def show_coming_soon(feature_name):
    """Displays a sleek popup for features currently in development."""
    st.toast(f"🚧 **{feature_name}** is currently in development. Coming soon!", icon="⏳")

# --- CSS Injection 
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
    .st-emotion-cache-1ejdgh8 {
    background-color: #0070F3 !important;
    }
 
    </style>
""", unsafe_allow_html=True)

# --- Session State Initialization ---
if "access_token" not in st.session_state:
    st.session_state.access_token = None
if "messages" not in st.session_state:
    st.session_state.messages = []
if "thread_id" not in st.session_state:
    st.session_state.thread_id = str(uuid.uuid4())  # Unique ID for this session/thread
if "query_data" not in st.session_state:
    st.session_state.query_data = None
if "status" not in st.session_state:
    st.session_state.status = None
if "counter" not in st.session_state:
    st.session_state.counter = 0

# ==========================================
# 🔒 THE DRIBBBLE-STYLE LOGIN PAGE
# ==========================================

if not st.session_state.access_token:
    st.write("<br><br><br>", unsafe_allow_html=True)
    
    left_brand, spacer, right_form = st.columns([1.2, 0.2, 1])
    
    with left_brand:
        st.markdown("<h1 style='font-size: 3.5rem; color: #ffffff;'>Datapilot AI<br>Insights</h1>", unsafe_allow_html=True)
        st.markdown("<p style='font-size: 1.2rem; color: #a0a0a0;'>Unlock the power of your data with conversational AI.<br>Secure, fast, and intelligent.</p>", unsafe_allow_html=True)
        
        if st.button("Read the Documentation", key="doc_btn"):
            show_coming_soon("Documentation Portal")

    with right_form:
        with st.container():
            st.markdown("### Welcome Back")
            tab_login, tab_register = st.tabs(["Log In", "Create Account"])
            
            # --- TAB 1: LOG IN ---
            with tab_login:
                with st.form("login_form"):
                    username = st.text_input("Email Address", placeholder="name@company.com")
                    password = st.text_input("Password", type="password", placeholder="••••••••")

                    if st.form_submit_button("Sign In", type="primary", width='stretch'):
                        with st.status("Authenticating...", expanded=True) as status:
                            try:
                                response = requests.post(LOGIN_URL, data={"username": username, "password": password}, timeout=60)
                                if response.status_code == 200:
                                    status.update(label="Login successful!", state="complete")
                                    st.session_state.access_token = response.json().get("access_token")
                                    st.rerun()
                                else:
                                    status.update(label="Login failed.", state="error")
                                    st.error(response.json().get("detail", "Login failed."))
                            except Exception as e:
                                status.update(label="Connection Error", state="error")
                                st.error(f"Something went wrong: {str(e)}")

            # --- TAB 2: REGISTER ---
            with tab_register:
                with st.form("register_form"):
                    new_username = st.text_input("Email Address")
                    new_password = st.text_input("Password", type="password")
                    
                    if st.form_submit_button("Sign Up", type="primary", width='stretch'):
                        with st.status("Preparing registration...", expanded=True) as status:
                            try:
                                headers={"Accept": "application/json", "Content-Type": "application/json"}
                                response = requests.post(REGISTER_URL, json={"username": new_username, "password": new_password}, timeout=60, headers=headers)
                                if response.status_code == 201:
                                    st.success("Account created successfully! You can now log in.")
                                else:
                                    status.update(label="Registration failed.", state="error")
                                    st.error(response.json().get("detail", "Registration failed."))
                            except Exception as e:
                                status.update(label="Connection Error", state="error")
                                st.error(f"Something went wrong: {str(e)}")

# ==========================================
# 📊 MAIN DASHBOARD (Logged In)
# ==========================================
else:
    # 1. Inject custom HTML/CSS
    custom_css = """
    <style>
        /* Create a fixed container for the app title */
        .fixed-header {
            position: fixed;
            top: 14px; /* Adjust vertical alignment */
            left: 320px; /* Adjust horizontal alignment to sit next to the sidebar toggle */
            z-index: 999999; /* Ensure it stays on top of other elements */
            font-family: 'Inter', sans-serif; /* Streamlit's default font style */
        }
        
        /* Style the text itself */
        .app-title {
            font-size: 20px;
            font-weight: 600;
            color: inherit; /* Inherits color from current theme (dark/light) */
            margin: 0;
        }
    </style>

    <div class="fixed-header">
        <p class="app-title">Datapilot</p>
    </div>
    """

    # Render the HTML
    st.markdown(custom_css, unsafe_allow_html=True)
    with st.sidebar:
        
        st.markdown("Menu")
       # ---------------------------------------------------------
    # ACCORDION 1: CONFIGURATIONS
    # ---------------------------------------------------------
    # expanded=False means it stays neatly closed until clicked
        with st.expander("Configurations", expanded=False):
            st.markdown("### System Status")
            st.success("🟢 Database Connected")
            st.info("🧠 LangGraph Memory: Active")
            
            st.divider()
            st.markdown("### Active AI Agents")
            st.caption("**Router:** `llama-3.1-8b-instant`")
            st.caption("**SQL:** `gemini-3.1-pro`")
            st.caption("**Analyst:** `llama-3.1-8b-instant`")
            
            st.divider()
            st.markdown("### Agent Parameters")
            creativity = st.slider("Analyst Creativity", 0.0, 1.0, 0.2, help="Lower = stricter math. Higher = narrative insights.")
        
            # ---------------------------------------------------------

        st.write("<br><br>", unsafe_allow_html=True) # Push logout to bottom
        if st.button("Logout", width="stretch"):
            st.session_state.access_token = None
            st.session_state.thread_id = None
            st.session_state.messages = []
            st.rerun()
    # --- Top Action Bar ---
 # --- Top Action Bar (Right Aligned) ---
# [4, 1, 1, 1] means the first column takes 4x more space, pushing others right
    spacer, col_share,col_delete = st.columns([4, 0.5,0.5])
    
    with col_share:
        if st.button("Share"): 
            show_coming_soon("Session Sharing")

    # with col_exit:
    #     if st.button("Exit"): 
    #         show_coming_soon("Exit Session")

    with col_delete:
        if st.button("Delete"): 
            st.session_state.messages = []
            st.rerun()

    st.markdown("<hr style='margin-top: 0; border: 0.5px solid #222;'>", unsafe_allow_html=True)
    # --- Main Chat Interface ---
    # st.markdown("## Datapilot")
    

    # --- Render Sample Questions (Only if chat is empty) ---
    if not st.session_state.messages:
        with st.expander("💡 Here are some sample questions", expanded=True):
            if st.button("Superhosts in Delhi", width="stretch"):
                st.toast("Copy and paste this into the chat below!", icon="💡")
            if st.button("Average price of Villas vs Apartments", width="stretch"):
                st.toast("Copy and paste this into the chat below!", icon="💡")



    # --- Render Chat History ---
    for i, msg in enumerate(st.session_state.messages):
        with st.chat_message(msg["role"]):
            if msg["role"] == "user":
                st.write(msg["content"])
            else:
                # Render the tabs directly inside the chat history loop!
                tabs = st.tabs(["Insights", "Data", "Code", "Visualizations", "Pivot Table"])
                
                with tabs[0]: st.write(msg.get("insight", "Query executed successfully."))
                
                with tabs[1]: 
                    df = msg.get("df")
                    if df is not None and not df.empty:
                        st.dataframe(df, width="stretch")
                    else:
                        st.info("No tabular data returned.")
                        
                with tabs[2]: st.code(msg.get("sql", "-- No SQL provided"), language="sql")
                
                with tabs[3]: 
                    st.markdown("#### Playgraph")
                    
                    df = msg.get("df")
                    if df is None or df.empty:
                        st.info("No data available to visualize.")
                    else:
                        # 1. Get the AI's default suggestion (if it exists)
                        viz_config = msg.get("viz_config", {})
                        charts = viz_config.get("suggested_visualizations", []) if viz_config else []
                        default_chart = charts[0] if charts else {"chart_type": "bar", "x_axis": df.columns[0], "y_axis": df.columns[0]}
                        
                        # 2. Build the UI Controls in a single row
                        ctrl1, ctrl2, ctrl3, ctrl4 = st.columns(4)
                        
                        all_columns = df.columns.tolist()
                        chart_types = ["bar", "line", "scatter", "area", "pie"]
                        
                        # Ensure defaults are valid (fallback to index 0 if LLM hallucinated)
                        def_type_idx = chart_types.index(default_chart.get("chart_type", "bar")) if default_chart.get("chart_type") in chart_types else 0
                        def_x_idx = all_columns.index(default_chart.get("x_axis")) if default_chart.get("x_axis") in all_columns else 0
                        def_y_idx = all_columns.index(default_chart.get("y_axis")) if default_chart.get("y_axis") in all_columns else 0
                        
                        with ctrl1:
                            c_type = st.selectbox("Chart Type", chart_types, index=def_type_idx, key=f"type_{i}")
                        with ctrl2:
                            x_col = st.selectbox("X-Axis", all_columns, index=def_x_idx, key=f"x_{i}")
                        with ctrl3:
                            y_col = st.selectbox("Y-Axis", all_columns, index=def_y_idx, key=f"y_{i}")
                        with ctrl4:
                            # Color is optional, add "None" to the start of the list
                            color_options = ["None"] + all_columns
                            color_col = st.selectbox("Group By (Color)", color_options, index=0, key=f"color_{i}")

                        # 3. Dynamic Plotly Rendering Engine
                        try:
                            # Set color to actual None if user selected the "None" string
                            plot_color = None if color_col == "None" else color_col
                            
                            if c_type == "bar":
                                fig = px.bar(df, x=x_col, y=y_col, color=plot_color)
                            elif c_type == "line":
                                fig = px.line(df, x=x_col, y=y_col, color=plot_color, markers=True)
                            elif c_type == "scatter":
                                fig = px.scatter(df, x=x_col, y=y_col, color=plot_color)
                            elif c_type == "area":
                                fig = px.area(df, x=x_col, y=y_col, color=plot_color)
                            elif c_type == "pie":
                                fig = px.pie(df, names=x_col, values=y_col)
                                
                            st.plotly_chart(fig, width='stretch', key=f"plot_{i}")
                            
                        except Exception as e:
                            st.warning("⚠️ This combination of columns cannot be rendered as this chart type. Try selecting different axes.")
                with tabs[4]:
                    df = msg.get("df")
                    if df is not None and not df.empty:
                        all_cols = df.columns.tolist()
                        numeric_cols = df.select_dtypes(include=['number']).columns.tolist()
                        p_col1, p_col2, p_col3, p_col4 = st.columns(4)
                        with p_col1:
                            pivot_rows = st.multiselect("Index",all_cols, key=f"p_row_{i}")
                        with p_col2:
                            pivot_cols = st.multiselect("Columns", all_cols, key=f"p_col_{i}")
                        with p_col3:
                            if not numeric_cols:
                                st.warning("No numerical columns available for math.")
                            pivot_values = st.multiselect("Value",numeric_cols, key=f"p_val_{i}")
                        with p_col4:
                            agg_funcs = ["sum", "mean", "count", "min", "max"]
                            pivot_agg = st.selectbox("Aggregation", agg_funcs, key=f"p_agg_{i}")

                        # Dynamic Pivot Engine
                        if pivot_rows and pivot_values:
                            try:
                                pivot_df = pd.pivot_table(
                                    df,
                                    index= pivot_rows,
                                    columns=pivot_cols if pivot_cols else None,
                                    values=pivot_values,
                                    aggfunc=pivot_agg
                                )
                                st.dataframe(pivot_df, width='stretch')

                            except Exception as e:
                                st.error(f" Pivot calculation error: {e}")

    # --- User Input Bar ---
    prompt = st.chat_input("Type your question here or type an SQL query to run...")

    if prompt:
        # Clear old query response
        st.session_state.query_data = None
        # 1. Display User Message instantly
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.write(prompt)

        # 2. Call the FastAPI Backend
        with st.chat_message("assistant"):
            with st.spinner("Analyzing database schema and generating insights..."):
                try:
                    query_headers = {"Authorization": f"Bearer {st.session_state.access_token}"}
                    payload = {
                        "question": prompt,
                        "thread_id": st.session_state.thread_id
                    }
                    response = requests.post(API_URL, json=payload, headers=query_headers)
                    
                    if response.status_code == 200:
                        api_data = response.json()
                        generated_sql = api_data.get("generated_sql", "-- SQL not found")
                        sql_results = api_data.get("result", [])
                        insight_text = api_data.get("result_summary", "No insights generated.")
                        viz_config = api_data.get("viz_config",{})
                        # Pre-build the DataFrame so we don't have to rebuild it on every Streamlit rerun
                        df = pd.DataFrame(sql_results) if sql_results else None
                        # Append the full payload to history
                        st.session_state.messages.append({
                            "role": "assistant",
                            "insight": insight_text,
                            "data": sql_results,
                            "df": df,
                            "sql": generated_sql,
                            "viz_config": viz_config
                        })
                        st.rerun()
                    elif response.status_code == 401:
                        st.error("Session expired. Please log in again.")
                        st.session_state.access_token = None
                        st.rerun()
                    else:
                        st.error(f"API Error {response.status_code}: {response.text}")
                                
                except requests.exceptions.ConnectionError:
                    st.error("🚨 Could not connect to the backend API. Is your FastAPI server running on port 8000?")