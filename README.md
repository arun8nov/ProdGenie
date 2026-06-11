# 🤖 ProdGenie — Productivity Analytics Engine

ProdGenie is a premium, high-performance analytics platform that converts your Google Sheets productivity tracker into a local SQLite database, allowing you to run sub-second search, aggregation, and natural-language queries via an AI-powered Text-to-SQL interface.

---

## 🌟 Key Features

* **AI Conversational Analyst**: Query your sheet data using natural language. The system converts your questions into optimized SQLite queries on the fly using **Google Gemini 2.5 Flash** (Primary) with an automatic fallback to **NVIDIA Llama 3.1-70B** (Backup).
* **Sub-Second SQL Caching**: Running vector embeddings or direct LLM contexts over 80k+ sheet rows is slow and expensive. ProdGenie maps sheet headers to a local SQLite schema for instant calculations.
* **🗃️ Data Vault**: Browse, filter, and inspect raw database records inside a clean table layout.
* **⚙️ Schema Manager**: Edit database column datatypes manually (TEXT, INTEGER, REAL, DATE, DATETIME) and re-cast schema structures instantly.
* **⚡ B-Tree Database Indexing**: Automatically generates optimized indexes on high-frequency query columns (`project`, `emp_id`, `work_done_by_emp_id`, `status`, `date`, `emp_name`) to speed up execution.
* **🔒 Data Quality Filters**: Filters out empty sheet rows during ingestion while preserving Google Sheet row numbers (`_sheet_row_number`) for alignment.

---

## 🛠️ Installation & Setup

### 1. Clone & Set Up the Virtual Environment
Navigate to the project directory and create a virtual environment:
```bash
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Configure Environment Variables
Create a `.env` file in the root folder with the following variables:
```env
ai_studio_api_key = "your_google_gemini_api_key"
nvidia_api_key = "your_nvidia_api_key"
sheet_url = "your_google_sheets_url"
sheet_name = "Task Entry"
```

### 3. Add Google Sheets OAuth Credentials
1. Place your Google API `credentials.json` file in the root directory.
2. Upon your first sync, a browser tab will prompt you to authorize read access to the Google Sheet. A local `token.json` will be saved to bypass future logins.

---

## 🚀 Run the Application

Start the Streamlit application:
```bash
streamlit run app.py
```

---

## 🔒 Security & Data Protection

This repository is configured to prevent accidental data leaks or credential exposures. The following files are strictly excluded from git tracking via `.gitignore`:
* `.env` (Secret API Keys)
* `credentials.json` & `token.json` (Google Sheets Access Credentials)
* `local_data.db` (Local SQLite database containing sheet data)
* `*.pkl` (Local data caches)
