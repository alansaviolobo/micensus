import io
import re
import os
import csv
import psycopg2
import urllib.request
import pandas as pd
from datetime import datetime

def load_env():
    if os.path.exists(".env"):
        with open(".env") as f:
            for line in f:
                if line.strip() and not line.startswith("#"):
                    key, value = line.strip().split("=", 1)
                    os.environ[key] = value

load_env()
INPUT_FILE = os.getenv("WB_INPUT_FILE")
OUTPUT_FILE = os.getenv("WB_OUTPUT_FILE")

def log(message):
    """Prints message to console and appends to output file."""
    print(message)
    with open(OUTPUT_FILE, "a", encoding="utf-8") as f:
        f.write(str(message) + "\n")

# DB Config
DB_HOST = os.getenv("DB_HOST")
DB_NAME = os.getenv("DB_NAME")
DB_USER = os.getenv("DB_USER")
DB_PASS = os.getenv("DB_PASS")
DB_PORT = os.getenv("DB_PORT")
SSLMODE = os.getenv("SSLMODE")

def get_db_connection():
    try:
        return psycopg2.connect(
            host=DB_HOST,
            database=DB_NAME,
            user=DB_USER,
            password=DB_PASS,
            port=DB_PORT,
            sslmode=SSLMODE
        )
    except Exception as e:
        print(f"Database connection failed: {e}")
        return None

# --- Validators ---

def main():
    # Clear output file
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write("")
        
    log(f"Reading data from {INPUT_FILE}...")
    
    if not os.path.exists(INPUT_FILE):
        log(f"Error: File not found at {INPUT_FILE}")
        return

    try:
        # Read the combined CSV file
        df = pd.read_csv(INPUT_FILE)
        # Convert DataFrame to list of dicts for compatibility with existing logic
        # Replace NaN with empty strings to match CSV behavior
        df = df.fillna("")
        reader = df.to_dict('records')
    except Exception as e:
        log(f"Failed to read file: {e}")
        return

    log("Connecting to database...")
    conn = get_db_connection()
    if not conn:
        log("Cannot proceed without DB connection.")
        return
    
    cursor = conn.cursor()

    # reader variable is already set above
    # reader = csv.DictReader(io.StringIO(csv_content))

    # Nested Grouping: Block -> Surveyor Name -> List of Errors
    grouped_issues = {}
    
    row_count = 0
    errors_found = 0
    revert_list = []
    
    print("\n*Validation Report* 📋\n")
    
    cursor.close()
    conn.close()

if __name__ == "__main__":
    main()
