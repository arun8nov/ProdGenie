import os
import re
import pandas as pd
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

# If modifying these scopes, delete the file token.json.
SCOPES = ['https://www.googleapis.com/auth/spreadsheets.readonly']

def sanitize_column_name(col: str) -> str:
    """Sanitizes a column name to conform to standard SQL syntax."""
    # Convert to lowercase
    s = col.strip().lower()
    # Replace spaces and any non-alphanumeric characters with underscore
    s = re.sub(r'[^a-z0-9_]', '_', s)
    # Deduplicate consecutive underscores
    s = re.sub(r'_+', '_', s)
    # Strip leading/trailing underscores
    s = s.strip('_')
    # SQL standard: columns cannot start with a digit
    if s and s[0].isdigit():
        s = 'col_' + s
    return s if s else "unnamed_column"

def extract_spreadsheet_id(url: str) -> str:
    """Extracts the spreadsheet ID from a Google Sheets URL."""
    match = re.search(r"/d/([a-zA-Z0-9-_]+)", url)
    if not match:
        raise ValueError(f"Could not extract Spreadsheet ID from URL: {url}")
    return match.group(1)

def get_sheets_service():
    """Handles OAuth authentication and returns the Google Sheets API service object."""
    creds = None
    if os.path.exists('token.json'):
        try:
            creds = Credentials.from_authorized_user_file('token.json', SCOPES)
        except Exception:
            os.remove('token.json')
            creds = None

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
            except Exception:
                flow = InstalledAppFlow.from_client_secrets_file(
                    'credentials.json', SCOPES)
                creds = flow.run_local_server(port=0)
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                'credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
            
        with open('token.json', 'w') as token:
            token.write(creds.to_json())
            
    return build('sheets', 'v4', credentials=creds)

def fetch_sheet_data(spreadsheet_url: str, sheet_name: str):
    """
    Fetches all rows from the specified sheet, sanitizes column names, 
    and returns a pandas DataFrame along with the column schema mapping dictionary.
    """
    spreadsheet_id = extract_spreadsheet_id(spreadsheet_url)
    service = get_sheets_service()
    
    sheet = service.spreadsheets()
    result = sheet.values().get(spreadsheetId=spreadsheet_id, range=sheet_name).execute()
    values = result.get('values', [])
    
    if not values:
        return pd.DataFrame(), {}
        
    # Read raw headers
    raw_headers = [col.strip() for col in values[0] if col.strip()]
    rows = values[1:]
    
    # Generate unique sanitized columns and build the schema mapping
    sanitized_headers = []
    schema_mapping = {}
    seen = set()
    
    for h in raw_headers:
        san = sanitize_column_name(h)
        # Handle duplicates in sheet header names
        orig_san = san
        counter = 1
        while san in seen:
            san = f"{orig_san}_{counter}"
            counter += 1
        seen.add(san)
        sanitized_headers.append(san)
        schema_mapping[san] = h
        
    # Pad/trim rows to ensure column alignment, skipping completely empty rows
    max_len = len(raw_headers)
    padded_rows = []
    original_row_numbers = []
    
    for idx, r in enumerate(rows):
        # Skip rows where all column values are null, empty, or whitespace-only
        if all(x is None or str(x).strip() == "" for x in r):
            continue
            
        if len(r) < max_len:
            r = r + [''] * (max_len - len(r))
        elif len(r) > max_len:
            r = r[:max_len]
        padded_rows.append(r)
        original_row_numbers.append(idx + 2) # Row 1 is header, so data starts at row 2
        
    df = pd.DataFrame(padded_rows, columns=sanitized_headers)
    
    # Add the correct 1-based original Google Sheet Row Number column for SQL tracking
    df.insert(0, '_sheet_row_number', original_row_numbers)
    schema_mapping['_sheet_row_number'] = "Sheet Row #"
    
    return df, schema_mapping
