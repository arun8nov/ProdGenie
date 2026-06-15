import os
import re
import requests
import pandas as pd
import streamlit as st
from dotenv import load_dotenv
import google.generativeai as genai

# Import local helpers
from google_sheets import fetch_sheet_data
import db_manager

# Load environment variables
load_dotenv()

# Page configuration
st.set_page_config(
    page_title="Productivity Tracker SQL RAG",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom premium aesthetics (emerald green theme with global font overrides and entrance animations)
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Outfit:wght@500;700&display=swap');
    
    /* Global font overrides - selective styling to avoid breaking icon fonts */
    html, body, .stMarkdown, .stText, p, li, label, input, button, select {
        font-family: 'Inter', sans-serif;
    }
    h1, h2, h3, h4, h5, h6, .main-title, .sidebar-title {
        font-family: 'Outfit', sans-serif;
    }
    
    /* Lock sidebar to single page viewport height & hide scrollbar */
    [data-testid="stSidebar"], [data-testid="stSidebar"] [class*="stSidebarUserContent"], [data-testid="stSidebar"] [data-testid="stVerticalBlock"] {
        max-height: 100vh !important;
        overflow-y: hidden !important;
    }
    
    .main-title {
        font-size: 2.5rem;
        background: linear-gradient(135deg, #107c41, #33c875);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        font-weight: 700;
        margin-bottom: 0px;
    }
    .subtitle {
        font-size: 1rem;
        color: #64748b;
        margin-bottom: 1.5rem;
    }
    .sidebar-title {
        font-weight: 700;
        font-size: 1.25rem;
        color: #107c41;
        margin-bottom: 0.5rem;
    }
    .badge {
        display: inline-block;
        padding: 0.25em 0.6em;
        font-size: 75%;
        font-weight: 700;
        line-height: 1;
        text-align: center;
        white-space: nowrap;
        vertical-align: baseline;
        border-radius: 0.375rem;
        margin-bottom: 10px;
    }
    .badge-success {
        color: #fff;
        background-color: #107c41;
    }
    .badge-warning {
        color: #000;
        background-color: #ffc107;
    }
    .stat-card {
        background: rgba(16, 124, 65, 0.05);
        border: 1px solid rgba(16, 124, 65, 0.15);
        border-radius: 8px;
        padding: 12px;
        margin-bottom: 12px;
        box-shadow: 0 2px 4px rgba(16, 124, 65, 0.02);
    }
    .stat-title {
        font-size: 0.8rem;
        color: #64748b;
        margin-bottom: 2px;
        font-weight: 500;
        text-transform: uppercase;
        letter-spacing: 0.5px;
    }
    .stat-value {
        font-size: 1.35rem;
        font-weight: 700;
        color: #107c41;
    }
    
    /* Animation for elements entering the page */
    @keyframes fadeInUp {
        from {
            opacity: 0;
            transform: translateY(12px);
        }
        to {
            opacity: 1;
            transform: translateY(0);
        }
    }
    
    /* Interactive chat bubbles with hover-lift effect */
    [data-testid="stChatMessage"] {
        border-radius: 16px;
        border: 1px solid rgba(16, 124, 65, 0.08);
        box-shadow: 0 4px 15px rgba(0,0,0,0.02);
        margin-bottom: 15px;
        animation: fadeInUp 0.4s ease-out forwards;
        transition: all 0.3s cubic-bezier(0.25, 0.8, 0.25, 1);
    }
    [data-testid="stChatMessage"]:hover {
        transform: translateY(-2px);
        box-shadow: 0 6px 20px rgba(16, 124, 65, 0.05);
        border-color: rgba(16, 124, 65, 0.2);
    }
    
    /* Column reference containers and badges */
    .column-reference-container {
        background: rgba(255, 255, 255, 0.65);
        backdrop-filter: blur(10px);
        -webkit-backdrop-filter: blur(10px);
        border: 1px solid rgba(16, 124, 65, 0.12);
        border-radius: 12px;
        padding: 8px 12px;
        margin-bottom: 15px;
        display: flex;
        flex-wrap: wrap;
        gap: 6px;
        animation: fadeInUp 0.5s ease-out forwards;
    }
    .column-badge {
        display: inline-block;
        padding: 5px 10px;
        font-size: 0.8rem;
        font-weight: 500;
        border-radius: 8px;
        background: rgba(16, 124, 65, 0.05);
        color: #107c41;
        border: 1px solid rgba(16, 124, 65, 0.12);
        cursor: pointer;
        transition: all 0.2s cubic-bezier(0.25, 0.8, 0.25, 1);
    }
    .column-badge:hover {
        background: #107c41;
        color: #ffffff;
        box-shadow: 0 4px 12px rgba(16, 124, 65, 0.25);
        transform: translateY(-1.5px);
    }
    
    /* Glassmorphism for expander widgets */
    .stExpander {
        border-radius: 10px !important;
        border: 1px solid rgba(16, 124, 65, 0.12) !important;
        background-color: rgba(255, 255, 255, 0.4) !important;
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.01) !important;
    }
    
    /* Button Hover Enhancements */
    button[kind="primary"] {
        transition: all 0.2s ease-in-out !important;
    }
    button[kind="primary"]:hover {
        background-color: #0d6334 !important;
        box-shadow: 0 4px 12px rgba(16, 124, 65, 0.3) !important;
        transform: translateY(-1px) !important;
    }
    button[kind="secondary"] {
        transition: all 0.2s ease-in-out !important;
    }
    button[kind="secondary"]:hover {
        background-color: rgba(16, 124, 65, 0.05) !important;
        border-color: #107c41 !important;
        color: #107c41 !important;
    }
    
    /* Pinned bottom input spacing */
    .block-container {
        padding-bottom: 110px !important;
    }
    </style>
""", unsafe_allow_html=True)

@st.cache_data
def get_base64_logo():
    import base64
    for filename in ["Logo.png", "logo.png"]:
        if os.path.exists(filename):
            with open(filename, "rb") as f:
                return base64.b64encode(f.read()).decode()
    return ""

# Helper to verify credentials exist
def get_config():
    api_key = os.getenv("ai_studio_api_key")
    sheet_url = os.getenv("sheet_url")
    sheet_name = os.getenv("sheet_name")
    nvidia_api_key = os.getenv("nvidia_api_key")
    app_password = os.getenv("app_password", "admin123")
    return api_key, sheet_url, sheet_name, nvidia_api_key, app_password

# Initialize configurations
api_key, sheet_url, sheet_name, nvidia_api_key, app_password = get_config()

def check_password():
    """Returns True if the user has entered the correct password."""
    def password_entered():
        if st.session_state["password"] == app_password:
            st.session_state["password_correct"] = True
            del st.session_state["password"]  # don't store password in session state
        else:
            st.session_state["password_correct"] = False

    if st.session_state.get("password_correct", False):
        return True

    # Show login UI
    logo_b64 = get_base64_logo()
    
    # Custom login card container styling
    st.markdown("""
        <style>
        /* Force dark radial background for full app container only during login */
        [data-testid="stAppViewContainer"] {
            background: radial-gradient(circle at 50% 50%, #082012 0%, #030a06 100%) !important;
        }
        
        /* Hide default Streamlit headers and footers on login page */
        [data-testid="stHeader"] {
            background-color: transparent !important;
        }
        
        .login-card {
            max-width: 440px;
            margin: 10% auto;
            padding: 40px;
            background: rgba(255, 255, 255, 0.03) !important;
            backdrop-filter: blur(20px) saturate(180%) !important;
            -webkit-backdrop-filter: blur(20px) saturate(180%) !important;
            border: 1px solid rgba(16, 124, 65, 0.25) !important;
            border-radius: 24px !important;
            box-shadow: 0 8px 32px 0 rgba(0, 250, 154, 0.05),
                        inset 0 0 15px rgba(16, 124, 65, 0.15) !important;
            text-align: center;
            color: #e2e8f0;
            animation: fadeInUp 0.8s cubic-bezier(0.16, 1, 0.3, 1) forwards;
        }
        
        .logo-glow-ring {
            display: inline-block;
            padding: 6px;
            border-radius: 20px;
            background: linear-gradient(135deg, rgba(16, 124, 65, 0.4), rgba(51, 200, 117, 0.4));
            box-shadow: 0 0 25px rgba(16, 124, 65, 0.35);
            margin-bottom: 20px;
            animation: pulseGlow 3s infinite ease-in-out;
        }
        
        @keyframes pulseGlow {
            0%, 100% { box-shadow: 0 0 20px rgba(51, 200, 117, 0.3); }
            50% { box-shadow: 0 0 35px rgba(51, 200, 117, 0.65); }
        }
        
        .login-logo {
            object-fit: contain;
            border-radius: 14px;
        }
        
        .login-title {
            font-family: 'Outfit', sans-serif;
            font-size: 2.3rem;
            font-weight: 700;
            background: linear-gradient(135deg, #33c875 0%, #107c41 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            margin-bottom: 4px;
            letter-spacing: -0.5px;
        }
        
        .login-subtitle {
            font-family: 'Inter', sans-serif;
            font-size: 0.78rem;
            color: #a7f3d0;
            opacity: 0.75;
            margin-bottom: 25px;
            text-transform: uppercase;
            letter-spacing: 1.5px;
            font-weight: 600;
        }
        
        /* Custom styled input fields for streamlit */
        .stTextInput > div > div > input {
            background-color: rgba(255, 255, 255, 0.05) !important;
            color: #ffffff !important;
            border: 1px solid rgba(16, 124, 65, 0.3) !important;
            border-radius: 12px !important;
            padding: 12px 16px !important;
            transition: all 0.3s ease !important;
            text-align: center;
        }
        
        .stTextInput > div > div > input:focus {
            border-color: #33c875 !important;
            box-shadow: 0 0 15px rgba(51, 200, 117, 0.3) !important;
            background-color: rgba(255, 255, 255, 0.08) !important;
        }
        
        /* Streamlit label styling */
        .stTextInput label {
            color: #cbd5e1 !important;
            font-size: 0.9rem !important;
            font-weight: 500 !important;
            margin-bottom: 8px !important;
        }
        </style>
    """, unsafe_allow_html=True)

    # Render Login Card
    st.markdown('<div class="login-card">', unsafe_allow_html=True)
    
    if logo_b64:
        st.markdown(
            f'<div class="logo-glow-ring">'
            f'<img class="login-logo" src="data:image/png;base64,{logo_b64}" width="75" height="75">'
            f'</div>',
            unsafe_allow_html=True
        )
    
    st.markdown('<div class="login-title">ProdGenie</div>', unsafe_allow_html=True)
    st.markdown('<div class="login-subtitle">Productivity Analytics Engine</div>', unsafe_allow_html=True)
    
    password_input = st.text_input("SECURE ACCESS GATEWAY", type="password", key="password", placeholder="••••••••", on_change=password_entered)
    
    if "password_correct" in st.session_state and not st.session_state["password_correct"]:
        st.error("😕 Access Denied. Please try again.")
        
    st.markdown('</div>', unsafe_allow_html=True)
    return False

if not check_password():
    st.stop()

class LLMResponse:
    def __init__(self, text):
        self.text = text

def execute_nvidia_fallback(prompt, temperature=0.2):
    """Executes SQL generation or analysis using NVIDIA API Catalog as the primary provider."""
    url = "https://integrate.api.nvidia.com/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {nvidia_api_key}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": "meta/llama-3.1-70b-instruct",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": temperature,
        "top_p": 0.7,
        "max_tokens": 1024,
        "stream": False
    }
    response = requests.post(url, headers=headers, json=payload)
    response.raise_for_status()
    return response.json()["choices"][0]["message"]["content"]

def execute_gemini_fallback(prompt, temperature=0.2):
    """Executes text generation using Gemini as a fallback option."""
    if not api_key:
        raise ValueError("Gemini API key is not configured.")
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel("gemini-2.5-flash")
    response = model.generate_content(
        prompt,
        generation_config=genai.GenerationConfig(temperature=temperature)
    )
    return response.text

def call_llm_with_fallback(prompt, temperature=0.2, max_retries=3):
    """
    Executes text generation using Google Gemini as the primary provider,
    and automatically falls back to NVIDIA API Catalog if Gemini fails or is unavailable.
    """
    # If Gemini API key is missing, go straight to NVIDIA
    if not api_key:
        st.warning("⚠️ Gemini API key is missing. Using NVIDIA as fallback...")
        try:
            res_text = execute_nvidia_fallback(prompt, temperature)
            return LLMResponse(res_text)
        except Exception as e:
            st.error(f"NVIDIA fallback failed: {e}")
            raise e

    import time
    delay = 2.0
    for attempt in range(max_retries):
        try:
            res_text = execute_gemini_fallback(prompt, temperature)
            return LLMResponse(res_text)
        except Exception as e:
            err_msg = str(e).lower()
            # If Gemini hits a rate limit or quota block, try falling back to NVIDIA
            if "429" in err_msg or "resource" in err_msg or "quota" in err_msg or "limit" in err_msg:
                if nvidia_api_key:
                    st.warning("⚠️ Gemini rate limit hit. Falling back to NVIDIA API (meta/llama-3.3-70b-instruct)...")
                    try:
                        res_text = execute_nvidia_fallback(prompt, temperature)
                        return LLMResponse(res_text)
                    except Exception as nv_err:
                        st.error(f"NVIDIA fallback failed: {nv_err}")
            
            if attempt == max_retries - 1:
                raise e
            
            # exponential backoff retry for Gemini
            time.sleep(delay)
            delay *= 2.0

def get_chat_history_context(messages, limit=5):
    """Formats the last 'limit' messages into a conversational context string for the SQL Generator."""
    context_parts = []
    for msg in messages[-limit:]:
        role = "User" if msg["role"] == "user" else "Assistant"
        content = msg["content"]
        context_parts.append(f"{role}: {content}")
        if msg["role"] == "assistant" and "sql_query" in msg and msg["sql_query"]:
            context_parts.append(f"  (Executed SQL: {msg['sql_query']})")
    return "\n".join(context_parts)

# Load DB stats
last_sync_time, total_records = db_manager.get_sync_info()

# Sidebar
with st.sidebar:
    logo_b64 = get_base64_logo()
    if logo_b64:
        st.markdown(
            f'<div style="display: flex; align-items: center; gap: 6px; margin-bottom: 12px; margin-top: -10px;">'
            f'<img src="data:image/png;base64,{logo_b64}" width="60" height="60" style="object-fit: contain; border-radius: 8px; margin-right: -4px;">'
            f'<div class="sidebar-title" style="margin: 0; font-size: 1.8rem; font-weight: 700; color: #107c41;">ProdGenie</div>'
            f'</div>',
            unsafe_allow_html=True
        )
    else:
        st.markdown('<div class="sidebar-title">📊 ProdGenie</div>', unsafe_allow_html=True)
    st.markdown("A powerful analytics platform that converts productivity tracker spreadsheets into a local SQL database, enabling fast, secure, and intelligent data exploration. ⭐")
    st.divider()

    # Navigation Menu (Placed at top of controls)
    st.markdown("### 🧭 Navigation")
    page = st.radio(
        "Select Page:",
        ["🤖 AI Conversational Analyst", "🗃️ Data Vault", "⚙️ Schema Manager"],
        label_visibility="collapsed"
    )
    st.divider()

    # Connection Status panel in compact expander
    with st.expander("🔌 Connection Status", expanded=False):
        if api_key:
            st.markdown('<span class="badge badge-success">Gemini API Configured (Primary)</span>', unsafe_allow_html=True)
        else:
            st.markdown('<span class="badge badge-warning">Missing Gemini API Key</span>', unsafe_allow_html=True)
            st.warning("Please add `ai_studio_api_key` to your `.env` file.")

        if nvidia_api_key:
            st.markdown('<span class="badge badge-success">NVIDIA API Configured (Fallback)</span>', unsafe_allow_html=True)
        else:
            st.markdown('<span class="badge badge-warning">NVIDIA Fallback Disabled</span>', unsafe_allow_html=True)
            st.warning("Please add `nvidia_api_key` to your `.env` file.")

    # Query Settings in compact expander
    with st.expander("⚙️ SQL Configurations", expanded=False):
        temperature = st.slider("Temperature", min_value=0.0, max_value=2.0, value=0.1, step=0.1)
        max_rows = st.slider("Max SQL Results Limit", min_value=10, max_value=500, value=100, step=10)

    st.divider()

    # Action buttons (Compact layout)
    st.markdown("### ⚡ Actions")
    col_btn1, col_btn2 = st.columns(2)
    with col_btn1:
        sync_pressed = st.button("🔄 Sync", use_container_width=True)
    with col_btn2:
        clear_pressed = st.button("♻️ Reset Cache", type="secondary", use_container_width=True)
        
    if sync_pressed:
        if not api_key:
            st.error("Cannot sync: Gemini API key is missing.")
        elif not os.path.exists("credentials.json"):
            st.error("Cannot sync: `credentials.json` is missing.")
        elif not sheet_url or not sheet_name:
            st.error("Cannot sync: `sheet_url` or `sheet_name` is missing from `.env`.")
        else:
            with st.spinner("Syncing spreadsheet data..."):
                try:
                    df, mapping = fetch_sheet_data(sheet_url, sheet_name)
                    if df.empty:
                        st.error("No data rows found in the sheet.")
                    else:
                        db_manager.save_data(df, mapping)
                        st.success("Sync Complete!")
                        st.rerun()
                except Exception as e:
                    st.error(f"Sync Failed: {e}")

    if clear_pressed:
        db_manager.clear_database()
        if os.path.exists("token.json"):
            os.remove("token.json")
        st.success("Local database cleared.")
        st.rerun()

# Main Dashboard Layout
title_col, toggle_col = st.columns([3, 1])
with title_col:
    logo_b64 = get_base64_logo()
    if logo_b64:
        st.markdown(
            f'<div style="display: flex; align-items: center; gap: 8px; margin-bottom: 8px;">'
            f'<img src="data:image/png;base64,{logo_b64}" width="85" height="85" style="object-fit: contain; border-radius: 12px; margin-right: -10px;">'
            f'<div class="main-title" style="margin: 0; line-height: 1.2;">Productivity Analytics Engine</div>'
            f'</div>',
            unsafe_allow_html=True
        )
    else:
        st.markdown('<div class="main-title">Productivity Analytics Engine</div>', unsafe_allow_html=True)
    st.markdown('<div class="subtitle" style="margin-top: 5px;">⭐ Unlock productivity insights by querying spreadsheet data with AI-powered Text-to-SQL analytics.</div>', unsafe_allow_html=True)
with toggle_col:
    st.markdown("<div style='height: 12px;'></div>", unsafe_allow_html=True)
    enable_analyst = st.toggle("🤖 Enable AI Analysis", value=False)

# Grid Stats
col1, col2, col3 = st.columns(3)
with col1:
    st.markdown(
        f'<div class="stat-card">'
        f'<div class="stat-title">Connected Spreadsheet</div>'
        f'<div class="stat-value" style="font-size:0.95rem; overflow:hidden; text-overflow:ellipsis; white-space:nowrap;">{sheet_name if sheet_name else "Not Connected"}</div>'
        f'</div>',
        unsafe_allow_html=True
    )
with col2:
    st.markdown(
        f'<div class="stat-card">'
        f'<div class="stat-title">Database Records</div>'
        f'<div class="stat-value">{total_records:,} rows</div>'
        f'</div>',
        unsafe_allow_html=True
    )
with col3:
    st.markdown(
        f'<div class="stat-card">'
        f'<div class="stat-title">Last Ingested Sync</div>'
        f'<div class="stat-value" style="font-size:1.1rem; line-height: 2rem;">{last_sync_time}</div>'
        f'</div>',
        unsafe_allow_html=True
    )

# Page 1: Conversational Chatbot
if page == "🤖 AI Conversational Analyst":
    if total_records == 0:
        st.info("👋 Welcome! Please click the **🔄 Sync Sheet Data** button in the sidebar to load and parse your Google Sheet data into the database.")
    else:
        # Fetch mapping and types for column reference
        mapping = db_manager.get_mapping()
        types = db_manager.get_types()
        
        # Display schema column helper at the top of chat area
        with st.expander("📋 Database Columns Reference Panel (Click to view fields for query)", expanded=True):
            st.markdown(
                "<div style='font-size: 0.88rem; color: #64748b; margin-bottom: 6px;'>"
                "Use these exact column names in your queries. Hover over a badge to see its original header and datatype."
                "</div>", 
                unsafe_allow_html=True
            )
            # Create a horizontal row of badges
            badge_html = []
            for col, orig in mapping.items():
                if col == "_sheet_row_number":
                    continue
                col_type = types.get(col, "TEXT")
                badge_html.append(
                    f'<span class="column-badge" title="Original Header: {orig} | SQLite Type: {col_type}">{col} ({col_type.lower()})</span>'
                )
            st.markdown(
                f'<div class="column-reference-container">{" ".join(badge_html)}</div>', 
                unsafe_allow_html=True
            )

        # Initialize chat history
        if "sql_messages" not in st.session_state:
            st.session_state.sql_messages = []

        # Display chat messages (Reordered: SQL & Table first, Analysis second)
        for msg in st.session_state.sql_messages:
            with st.chat_message(msg["role"]):
                if msg["role"] == "user":
                    st.markdown(msg["content"])
                else:
                    # Assistant: first show SQL, then table, then analysis report
                    if "sql_query" in msg and msg["sql_query"]:
                        st.markdown("**Executed SQL Query:**")
                        st.code(msg["sql_query"], language="sql")
                    if "sql_results" in msg and msg["sql_results"] is not None:
                        results_df = pd.DataFrame(msg["sql_results"])
                        if results_df.empty:
                            st.info("No matching records found.")
                        else:
                            st.markdown(f"**Query Results ({len(results_df):,} rows):**")
                            st.dataframe(results_df, hide_index=True)
                    st.markdown(msg["content"])

        # Handle user query
        if user_query := st.chat_input("Ask a question (e.g. 'How many tasks are completed?' or 'List latest 5 tasks'):"):
            st.chat_message("user").markdown(user_query)
            st.session_state.sql_messages.append({"role": "user", "content": user_query})

            with st.chat_message("assistant"):
                with st.spinner("Generating and executing SQL query..."):
                    try:
                        # 1. Get database DDL schema representation
                        schema_ddl = db_manager.get_schema_ddl()
                        
                        # Get conversational context from previous messages (last 5)
                        chat_history_ctx = get_chat_history_context(st.session_state.sql_messages[:-1], limit=5)
                        
                        sql_prompt = f"""Write a SQLite query for the user's question.

Schema:
{schema_ddl}

History:
{chat_history_ctx if chat_history_ctx else "None"}

User's Question: {user_query}

Instructions:
1. Return ONLY SQLite SELECT in ```sql block. No text/backticks. Max {max_rows} rows.
2. SQLite: Use standard operators (||, LIKE) and functions (date).
3. strftime lacks %b and %y. Format month abbreviations and 2-digit years manually.
"""
                        response = call_llm_with_fallback(sql_prompt, temperature=temperature)
                        
                        # Parse the generated SQL query out of the markdown blocks
                        raw_response = response.text.strip()
                        sql_match = re.search(r"```(?:sqlite|sql)?\s*(.*?)\s*```", raw_response, re.DOTALL | re.IGNORECASE)
                        sql_query = sql_match.group(1).strip() if sql_match else raw_response
                        
                        # Strip any trailing semicolons or markdown tags if formatting was loose
                        sql_query = sql_query.replace("`", "").strip()
                        if sql_query.lower().startswith("sqlite"):
                            sql_query = sql_query[6:].strip()
                        elif sql_query.lower().startswith("sql"):
                            sql_query = sql_query[3:].strip()
                            
                        # 3. Execute query on local SQLite database
                        df_result = db_manager.execute_query(sql_query)
                        restored_df = db_manager.restore_column_names(df_result)
                        
                        # 4. Generate Analyst Report (Agent 2 - Token-Minimized)
                        if df_result.empty:
                            analyst_answer = "No matching records found in the database."
                        elif not enable_analyst:
                            analyst_answer = "Here are the SQL query execution results:"
                        else:
                            # Truncate data to first 20 rows to minimize token waste
                            df_sample = df_result.head(20)
                            
                            analyst_prompt = f"""Analyze query results and answer the user question.

User Question: {user_query}
SQL Query: {sql_query}
Total Rows: {len(df_result)}

Sample Data:
{df_sample.to_string(index=False)}

Instructions:
1. Brief bullet points (max 3-4) in plain language. No SQL/technical terms.
2. Focus strictly on answering the question.
"""
                            # Request analysis from Primary (NVIDIA) or Fallback (Gemini)
                            analyst_response = call_llm_with_fallback(analyst_prompt, temperature=0.3)
                            analyst_answer = analyst_response.text
                            
                        # 5. Render output in UI (Reordered: SQL & Table first, Analysis second)
                        st.markdown("**Executed SQL Query:**")
                        st.code(sql_query, language="sql")
                        
                        if not restored_df.empty:
                            st.markdown(f"**Query Results ({len(restored_df):,} rows):**")
                            st.dataframe(restored_df, hide_index=True)
                            
                        st.markdown("---")
                        st.markdown(analyst_answer)
                            
                        # Save assistant message to session state
                        st.session_state.sql_messages.append({
                            "role": "assistant",
                            "content": analyst_answer,
                            "sql_query": sql_query,
                            "sql_results": restored_df.to_dict('records') if not restored_df.empty else None
                        })
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error executing query: {e}")

# Page 2: Raw SQLite Data Browser
elif page == "🗃️ Data Vault":
    if total_records > 0:
        st.markdown("### SQLite Raw Database Browser")
        st.markdown("Use standard SQL clauses or keywords below to query and inspect your local table.")
        
        # Search & Filter
        col_filter1, col_filter2 = st.columns([3, 1])
        with col_filter1:
            search_query = st.text_input("🔍 Search rows (e.g. filter by keyword/term):", value="", placeholder="Leave blank to show all rows")
        with col_filter2:
            limit_rows = st.number_input("Limit display rows:", min_value=10, max_value=5000, value=500, step=100)
            
        # Build SQL based on search input
        if search_query.strip():
            columns_mapping = db_manager.get_mapping()
            # Construct a SQL query that searches across ALL columns using LIKE
            like_clauses = []
            for col in columns_mapping.keys():
                like_clauses.append(f"{col} LIKE '%{search_query}%'")
            sql_browse = f"SELECT * FROM sheet_table WHERE {' OR '.join(like_clauses)} LIMIT {limit_rows}"
        else:
            sql_browse = f"SELECT * FROM sheet_table LIMIT {limit_rows}"
            
        try:
            df_browse = db_manager.execute_query(sql_browse)
            df_browse_restored = db_manager.restore_column_names(df_browse)
            
            # Display stats
            st.caption(f"Showing {len(df_browse_restored)} records matching filter (out of {total_records:,} total records)")
            st.dataframe(df_browse_restored, use_container_width=True, hide_index=True)
        except Exception as e:
            st.error(f"Error loading browse data: {e}")
    else:
        st.info("No records inside SQLite cache. Sync the spreadsheet to browse data.")

# Page 3: Schema Manager
elif page == "⚙️ Schema Manager":
    st.markdown("### ⚙️ Database Table Schema & Mappings")
    mapping = db_manager.get_mapping()
    types = db_manager.get_types()
    
    if mapping:
        st.markdown(f"**Local SQLite DB File:** `local_data.db`")
        st.markdown(f"**Total Columns Mapped:** `{len(mapping)}` columns")
        
        # Display schema table
        schema_rows = []
        for col, orig in mapping.items():
            col_type = "INTEGER" if col == "_sheet_row_number" else types.get(col, "TEXT")
            schema_rows.append({
                "Sanitized SQL Column": col,
                "Original Sheet Header": orig,
                "SQLite Data Type": col_type
            })
            
        st.dataframe(pd.DataFrame(schema_rows), use_container_width=True, hide_index=True)
        
        # Interactive Schema Editor
        st.divider()
        st.markdown("### 🛠️ Edit Column Data Types")
        st.markdown("If any column type was not detected correctly, select the correct type below and apply the changes to the database.")
        
        with st.form("schema_editor_form"):
            new_types = {}
            # Display inputs in a 2-column grid to save vertical space
            grid_cols = st.columns(2)
            
            # Filter out metadata column for editing
            cols_to_edit = [c for c in mapping.keys() if c != "_sheet_row_number"]
            
            for idx, col in enumerate(cols_to_edit):
                orig_name = mapping[col]
                current_type = types.get(col, "TEXT")
                
                grid_index = idx % 2
                with grid_cols[grid_index]:
                    selected_type = st.selectbox(
                        f"{orig_name} ({col})",
                        options=["TEXT", "INTEGER", "REAL", "DATE", "DATETIME"],
                        index=["TEXT", "INTEGER", "REAL", "DATE", "DATETIME"].index(current_type),
                        key=f"type_select_{col}"
                    )
                    new_types[col] = selected_type
                    
            submitted = st.form_submit_button("💾 Save & Re-cast Database Schema", use_container_width=True)
            if submitted:
                try:
                    db_manager.reapply_schema(new_types)
                    st.success("Schema types updated and database re-casted successfully!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Error reapplying schema: {e}")
        
        st.divider()
        with st.expander("👁️ View Text Schema Passed to Gemini"):
            st.code(db_manager.get_schema_description())
    else:
        st.info("No column mappings cached. Sync the sheet to view schema diagnostics.")
