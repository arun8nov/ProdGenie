import os
import json
import sqlite3
import pandas as pd
from datetime import datetime

DB_FILE = "local_data.db"
SCHEMA_FILE = "schema_mapping.json"
RAW_DATA_FILE = "raw_sheet_data.pkl"
TABLE_NAME = "sheet_table"

def infer_column_type(series: pd.Series) -> str:
    """Infers the SQLite datatype of a column based on its Pandas series values."""
    # Clean up empty strings or whitespace
    cleaned = series.replace(r'^\s*$', None, regex=True).dropna()
    if cleaned.empty:
        return "TEXT"

    # Try converting to numeric (integer or float)
    try:
        numeric = pd.to_numeric(cleaned, errors='raise')
        # Check if all numbers can be integers
        if all(abs(x - round(x)) < 1e-9 for x in numeric):
            return "INTEGER"
        return "REAL"
    except (ValueError, TypeError):
        pass

    # Try converting to date or datetime (only if it contains symbols like '-' or '/' or ':')
    sample_vals = cleaned.head(50)
    has_date_symbols = any(any(c in str(v).lower() for c in ['-', '/', ':', 'jan', 'feb', 'mar', 'apr', 'may', 'jun', 'jul', 'aug', 'sep', 'oct', 'nov', 'dec']) for v in sample_vals)
    
    if has_date_symbols:
        try:
            # Let pandas parse standard dates (including formats like 5-Dec-2025)
            parsed = pd.to_datetime(cleaned, errors='raise')
            # Check if it has any hours/minutes/seconds
            if all(t.time() == datetime.min.time() for t in parsed):
                return "DATE"
            return "DATETIME"
        except Exception:
            pass

    return "TEXT"

def cast_dataframe(df: pd.DataFrame, type_mapping: dict) -> pd.DataFrame:
    """Casts raw string DataFrame columns to standard database types (and normalizes dates)."""
    casted_df = df.copy()
    for col in casted_df.columns:
        if col.startswith('_'):  # Skip internal metadata columns
            continue

        target_type = type_mapping.get(col, "TEXT")
        # Replace empty strings/spaces with None/NaN for clean SQL NULL insertion
        series_cleaned = casted_df[col].replace(r'^\s*$', None, regex=True)

        if target_type == "INTEGER":
            casted_df[col] = pd.to_numeric(series_cleaned, errors='coerce').round().astype("Int64")
        elif target_type == "REAL":
            casted_df[col] = pd.to_numeric(series_cleaned, errors='coerce').astype(float)
        elif target_type in ("DATE", "DATETIME"):
            try:
                parsed = pd.to_datetime(series_cleaned, errors='coerce')
                if target_type == "DATE":
                    # Format standard date: YYYY-MM-DD
                    casted_df[col] = parsed.dt.strftime('%Y-%m-%d')
                else:
                    # Format standard datetime: YYYY-MM-DD HH:MM:SS
                    casted_df[col] = parsed.dt.strftime('%Y-%m-%d %H:%M:%S')
            except Exception:
                casted_df[col] = series_cleaned.astype(str)
        else:  # TEXT
            # Clean up string columns
            casted_df[col] = series_cleaned.astype(str).replace('None', '')

    return casted_df

def create_indexes(conn):
    """Creates database indexes on key fields to accelerate SQLite queries."""
    index_queries = [
        "CREATE INDEX IF NOT EXISTS idx_project ON sheet_table (project);",
        "CREATE INDEX IF NOT EXISTS idx_emp_id ON sheet_table (emp_id);",
        "CREATE INDEX IF NOT EXISTS idx_work_done_by_emp_id ON sheet_table (work_done_by_emp_id);",
        "CREATE INDEX IF NOT EXISTS idx_status ON sheet_table (status);",
        "CREATE INDEX IF NOT EXISTS idx_date ON sheet_table (date);",
        "CREATE INDEX IF NOT EXISTS idx_emp_name ON sheet_table (emp_name);"
    ]
    cursor = conn.cursor()
    for q in index_queries:
        try:
            cursor.execute(q)
        except Exception:
            pass  # Fail-safe in case a column doesn't exist in the current sheet

def save_data(df_raw: pd.DataFrame, schema_mapping: dict):
    """
    Saves raw DataFrame to raw_sheet_data.pkl, infers/applies schema types,
    and updates SQLite database.
    """
    # 1. Save raw DataFrame
    df_raw.to_pickle(RAW_DATA_FILE)

    # 2. Check for existing type settings (manual overrides)
    existing_types = {}
    if os.path.exists(SCHEMA_FILE):
        try:
            with open(SCHEMA_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                existing_types = data.get("types", {})
        except Exception:
            pass

    # 3. Build datatype mapping (preserve manual overrides or infer)
    type_mapping = {}
    for col in df_raw.columns:
        if col.startswith('_'):
            continue
        if col in existing_types:
            type_mapping[col] = existing_types[col]
        else:
            type_mapping[col] = infer_column_type(df_raw[col])

    # 4. Cast the DataFrame
    df_casted = cast_dataframe(df_raw, type_mapping)

    # 5. Save casted DataFrame to SQLite
    conn = sqlite3.connect(DB_FILE)
    try:
        df_casted.to_sql(TABLE_NAME, conn, if_exists="replace", index=False)
        create_indexes(conn)

        # 6. Save schema mapping JSON
        mapping_data = {
            "last_sync": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "columns": schema_mapping,
            "types": type_mapping
        }
        with open(SCHEMA_FILE, "w", encoding="utf-8") as f:
            json.dump(mapping_data, f, indent=2, ensure_ascii=False)
    finally:
        conn.close()

def reapply_schema(type_mapping: dict):
    """Loads raw sheet data cache, casts it with new type mapping, and overwrites DB."""
    if not os.path.exists(RAW_DATA_FILE):
        raise FileNotFoundError("Raw sheet data cache not found. Please sync the sheet first.")

    df_raw = pd.read_pickle(RAW_DATA_FILE)

    # Cast DataFrame
    df_casted = cast_dataframe(df_raw, type_mapping)

    # Write to SQLite
    conn = sqlite3.connect(DB_FILE)
    try:
        df_casted.to_sql(TABLE_NAME, conn, if_exists="replace", index=False)
        create_indexes(conn)

        # Update JSON schema mapping
        data = {"columns": {}, "types": {}}
        if os.path.exists(SCHEMA_FILE):
            try:
                with open(SCHEMA_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
            except Exception:
                pass

        data["types"] = type_mapping

        with open(SCHEMA_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    finally:
        conn.close()

def clear_database():
    """Clears local SQLite database file, schema caches, and raw pickle cache."""
    for filepath in [DB_FILE, SCHEMA_FILE, RAW_DATA_FILE]:
        if os.path.exists(filepath):
            try:
                os.remove(filepath)
            except Exception:
                pass

def execute_query(sql_query: str) -> pd.DataFrame:
    """Executes a SQL query on the local database and returns the result as a DataFrame."""
    conn = sqlite3.connect(DB_FILE)
    try:
        df = pd.read_sql_query(sql_query, conn)
        return df
    finally:
        conn.close()

def get_sync_info():
    """Returns the last sync time and total records in the database."""
    last_sync = "Never"
    total_records = 0

    if os.path.exists(SCHEMA_FILE):
        try:
            with open(SCHEMA_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                last_sync = data.get("last_sync", "Never")
        except Exception:
            pass

    if os.path.exists(DB_FILE):
        conn = sqlite3.connect(DB_FILE)
        try:
            cursor = conn.cursor()
            cursor.execute(f"SELECT COUNT(*) FROM {TABLE_NAME}")
            total_records = cursor.fetchone()[0]
        except Exception:
            pass
        finally:
            conn.close()

    return last_sync, total_records

def get_mapping() -> dict:
    """Loads and returns the cached column mapping dict."""
    if os.path.exists(SCHEMA_FILE):
        try:
            with open(SCHEMA_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data.get("columns", {})
        except Exception:
            pass
    return {}

def get_types() -> dict:
    """Loads and returns the cached column types dict."""
    if os.path.exists(SCHEMA_FILE):
        try:
            with open(SCHEMA_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data.get("types", {})
        except Exception:
            pass
    return {}

def get_schema_ddl() -> str:
    """Generates a compact SQL CREATE TABLE representation of the schema for LLM prompt optimization."""
    columns_mapping = get_mapping()
    types_mapping = get_types()
    if not columns_mapping:
        return "No schema available."
        
    ddl_lines = []
    for col, orig in columns_mapping.items():
        col_type = "INTEGER" if col == "_sheet_row_number" else types_mapping.get(col, "TEXT").upper()
        ddl_lines.append(f"  {col} {col_type}, -- {orig}")
        
    ddl = f"CREATE TABLE {TABLE_NAME} (\n" + ",\n".join(ddl_lines) + "\n);"
    return ddl

def get_schema_description() -> str:
    """Generates a text description of the table schema to feed into the Gemini LLM prompt."""
    columns_mapping = get_mapping()
    types_mapping = get_types()
    if not columns_mapping:
        return "No schema available."

    desc = f"Table name: {TABLE_NAME}\nColumns description:\n"
    for col, orig in columns_mapping.items():
        if col == "_sheet_row_number":
            desc += f"- {col} (integer): The 1-based row number of the record in the original Google Sheet.\n"
        else:
            col_type = types_mapping.get(col, "TEXT").upper()
            desc += f"- {col} ({col_type}): Represents values from the column originally named '{orig}' in the sheet.\n"
    return desc

def restore_column_names(df: pd.DataFrame) -> pd.DataFrame:
    """Renames SQL-sanitized column names in the output DataFrame back to their original sheet headers."""
    columns_mapping = get_mapping()
    if not columns_mapping:
        return df

    rename_dict = {}
    for col in df.columns:
        if col in columns_mapping:
            rename_dict[col] = columns_mapping[col]
    return df.rename(columns=rename_dict)
