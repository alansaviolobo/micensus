#!/usr/bin/env python3
"""
Script to automate login to wrcensus-spring.mowr.gov.in and download schedules Excel file.
Uses anti-captcha.com service to solve captcha challenges.
"""

import os
import json
import time
import glob
import shutil
import requests
import pandas as pd
import datetime
import concurrent.futures
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# Configuration
def load_env():
    if os.path.exists(".env"):
        with open(".env") as f:
            for line in f:
                if line.strip() and not line.startswith("#"):
                    key, value = line.strip().split("=", 1)
                    os.environ[key] = value

load_env()
LOGIN_URL = os.getenv("LOGIN_URL")
ANTI_CAPTCHA_API_KEY = os.getenv("ANTI_CAPTCHA_API_KEY")
DOWNLOAD_DIR = os.path.join(os.getcwd(), "downloads")
CREDENTIALS_STR = os.getenv("CREDENTIALS", "[]")
CREDENTIALS = json.loads(CREDENTIALS_STR[1:-1])

# Taluka to login username mapping
TALUKA_LOGIN_MAP = {
    "Bardez": "bdobardez@gmail.com",
    "Bicholim": "bicholimbdo@gmail.com",
    "BicholimCity": "ee6-wrd.goa@gov.in",
    "Canacona": "bdo_can@yahoo.in",
    "CanaconaCity": "wrdcanacona1@gmail.com",
    "CuncolimCity": "wrdwd2@gmail.com",
    "CurchoremCity": "ee14-wrd.goa@gov.in",
    "Dharbandora": "bdo-darbandora.goa@nic.in",
    "MapusaCity": "aeiimapusa@gmail.com",
    "MargaoCity": "sub.division.1.wd2.wrd@gmail.com",
    "Mormugao": "bdomormugao2013@gmail.com",
    "PanajiCity": "wrdsubiwdiporvorim@gmail.com",
    "Pernem": "pernembdo@gmail.com",
    "PernemCity": "ee7-wrd.goa@gov.in",
    "Ponda": "sdiv.wdii.wrdponda@gmail.com",
    "PondaCity": "ee11-wrd.goa@gov.in",
    "Quepem": "bdo.quepem@gmail.com",
    "QuepemCity": "quepemwrd@gmail.com",
    "Sanguem": "bdo-sanguem.goa@nic.in",
    "SanguemCity": "ee10-wrd.goa@nic.in",
    "SankhaliCity": "ae1wd6wrd@gmail.com",
    "Salcete": "bdosalcete@yahoo.co.in",
    "Sattari": "bdo-sattari.goa@nic.in",
    "Tiswadi": "bdo-tiswadi@gmail.com",
    "ValpoiCity": "bdosattari45@gmail.com",
    "VascoCity": "bdo-mormugao.goa@nic.in",
}

# Inverse map for easy lookup
LOGIN_TALUKA_MAP = {v: k for k, v in TALUKA_LOGIN_MAP.items()}

# Create directory if it doesn't exist (but don't clear it yet)
os.makedirs(DOWNLOAD_DIR, exist_ok=True)
print(f"Download directory ready: {DOWNLOAD_DIR}\n")


def wait_for_download_and_rename(download_dir, taluka_name, timeout=60):
    """
    Wait for a new .xlsx file to appear in the download directory and rename it.
    
    Args:
        download_dir: Directory where the file is being downloaded
        taluka_name: Name to rename the file to
        timeout: Maximum time to wait in seconds
        
    Returns:
        str: Path to the renamed file, or None if failed
    """
    print(f"Waiting for download to complete for {taluka_name}...")
    start_time = time.time()
    
    while time.time() - start_time < timeout:
        # Look for .xlsx files that are NOT temporary chrome downloads (.crdownload)
        xlsx_files = glob.glob(os.path.join(download_dir, "Schedules*.csv"))
        # Also check for .crdownload to see if download is in progress
        cr_files = glob.glob(os.path.join(download_dir, "*.crdownload"))
        
        # If we have an xlsx file and no crdownload files, or if the xlsx file is new
        # We need to be careful because there might be other files from other threads
        # But each thread should ideally have a unique filename or we rename it immediately
        
        # A better approach: find the most recently created .xlsx file that is not already renamed
        if xlsx_files:
            # Sort by modification time
            xlsx_files.sort(key=os.path.getmtime, reverse=True)
            newest_file = xlsx_files[0]
            
            # Check if this file was created AFTER we started waiting
            if os.path.getmtime(newest_file) >= start_time - 2: # 2s buffer
                # Check if it's still being written (size changing)
                last_size = -1
                while True:
                    current_size = os.path.getsize(newest_file)
                    if current_size == last_size and current_size > 0:
                        break
                    last_size = current_size
                    time.sleep(1)
                
                # Rename the file
                new_path = os.path.join(download_dir, f"{taluka_name}.csv")
                try:
                    # If target exists, remove it first
                    if os.path.exists(new_path):
                        os.remove(new_path)
                    os.rename(newest_file, new_path)
                    print(f"✅ Renamed {os.path.basename(newest_file)} to {taluka_name}.csv")
                    return new_path
                except Exception as e:
                    print(f"Error renaming file: {e}")
                    return None
        
        time.sleep(1)
        
    print(f"❌ Timeout waiting for download of {taluka_name}")
    return None


def solve_captcha_with_anticaptcha(image_base64):
    """
    Solve captcha using anti-captcha.com service.
    
    Args:
        image_base64: Base64 encoded captcha image
        
    Returns:
        str: Solved captcha text
    """
    # Create task
    create_task_url = "https://api.anti-captcha.com/createTask"
    task_data = {
        "clientKey": ANTI_CAPTCHA_API_KEY,
        "task": {
            "type": "ImageToTextTask",
            "body": image_base64,
            "phrase": False,
            "case": False,
            "numeric": 0,
            "math": False,
            "minLength": 0,
            "maxLength": 0
        }
    }
    
    response = requests.post(create_task_url, json=task_data)
    result = response.json()
    
    if result.get("errorId") != 0:
        raise Exception(f"Anti-captcha error: {result.get('errorDescription')}")
    
    task_id = result.get("taskId")
    print(f"Captcha task created with ID: {task_id}")
    
    # Poll for result
    get_result_url = "https://api.anti-captcha.com/getTaskResult"
    for _ in range(30):  # Try for up to 60 seconds
        time.sleep(2)
        result_data = {
            "clientKey": ANTI_CAPTCHA_API_KEY,
            "taskId": task_id
        }
        response = requests.post(get_result_url, json=result_data)
        result = response.json()
        
        if result.get("status") == "ready":
            captcha_text = result.get("solution", {}).get("text")
            print(f"Captcha solved: {captcha_text}")
            return captcha_text
        elif result.get("errorId") != 0:
            raise Exception(f"Anti-captcha error: {result.get('errorDescription')}")
    
    raise Exception("Captcha solving timeout")


def download_schedules_for_user(username, password):
    """
    Login and download schedules Excel file for a specific user.
    
    Args:
        username: User's email/username
        password: User's password
        
    Returns:
        bool: True if successful, False otherwise
    """
    # Setup Chrome options
    chrome_options = Options()
    chrome_options.add_argument("--window-size=2240,1440")
    chrome_options.add_experimental_option("prefs", {
        "download.default_directory": DOWNLOAD_DIR,
        "download.prompt_for_download": False,
        "download.directory_upgrade": True,
        "safebrowsing.enabled": True
    })
    # chrome_options.add_argument("--headless")  # Uncomment to run headless
    chrome_options.add_argument("--headless")  # Set to headless for parallel execution
    
    driver = webdriver.Chrome(options=chrome_options)
    
    try:
        print(f"\n{'='*60}")
        print(f"Processing account: {username}")
        print(f"{'='*60}")
        
        print(f"Navigating to {LOGIN_URL}...")
        driver.get(LOGIN_URL)
        
        # Wait for page to load
        wait = WebDriverWait(driver, 10)
        
        MAX_RETRIES = 3
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                print(f"Login attempt {attempt}/{MAX_RETRIES}...")
                
                # Refresh page if this is a retry to get new captcha
                if attempt > 1:
                    print("Refreshing page for retry...")
                    driver.refresh()
                    time.sleep(2)
                
                # Fill in username (email field)
                print("Filling in credentials...")
                username_field = wait.until(EC.presence_of_element_located((By.ID, "email")))
                username_field.clear()
                username_field.send_keys(username)
                
                # Fill in password
                password_field = driver.find_element(By.ID, "password")
                password_field.clear()
                password_field.send_keys(password)
                
                # Get captcha image
                print("Retrieving captcha image...")
                captcha_img = driver.find_element(By.ID, "captchaImage")
                
                # Get captcha image as base64
                captcha_base64 = driver.execute_script("""
                    var canvas = document.createElement('canvas');
                    var context = canvas.getContext('2d');
                    var img = arguments[0];
                    canvas.height = img.naturalHeight;
                    canvas.width = img.naturalWidth;
                    context.drawImage(img, 0, 0);
                    return canvas.toDataURL('image/png').substring(22);
                """, captcha_img)
                
                # Solve captcha
                print("Solving captcha...")
                captcha_text = solve_captcha_with_anticaptcha(captcha_base64)
                
                # Fill captcha
                captcha_field = driver.find_element(By.ID, "captchaInput")
                captcha_field.clear()
                captcha_field.send_keys(captcha_text)
                
                # Submit login form
                print("Submitting login form...")
                login_button = driver.find_element(By.ID, "encryptSubmitBtn")
                login_button.click()
                
                # Wait for login to complete
                time.sleep(3)
                
                # Check if login was successful
                if "login" not in driver.current_url.lower():
                    print(f"✅ Login successful for {username}!")
                    break
                else:
                    print(f"⚠️ Login attempt {attempt} failed.")
                    # If this was the last attempt, return False
                    if attempt == MAX_RETRIES:
                        print(f"❌ All login attempts failed for {username}.")
                        return False
            
            except Exception as e:
                print(f"⚠️ Error during login attempt {attempt}: {e}")
                if attempt == MAX_RETRIES:
                    return False
        
        # Wait a bit for dashboard to fully load
        time.sleep(2)
        
        # Try to open sidebar menu if it's collapsed
        try:
            print("Opening navigation menu...")
            menu_button = driver.find_element(By.CSS_SELECTOR, "a.nav-item.nav-link.px-0.me-xl-4")
            menu_button.click()
            time.sleep(1)
        except:
            print("Menu already open or not found, continuing...")
        
        # Navigate to schedules page
        print("Looking for schedules link...")
        schedules_link = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "a.menu-link[href*='surveys']")))
        schedules_link.click()
        
        time.sleep(2)
        
        # Find and click Excel button (opens privacy modal)
        print("Clicking EXCEL button...")
        excel_button = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, 'button[data-bs-target="#privacyCheckModal"]')))
        excel_button.click()
        
        # Wait for modal to appear
        time.sleep(1)
        
        # Check the privacy checkbox
        print("Accepting privacy terms...")
        privacy_checkbox = wait.until(EC.element_to_be_clickable((By.ID, "agreePrivacyCheck")))
        privacy_checkbox.click()
        
        # Click the final download button in the modal
        print("Downloading Excel file...")
        download_button = wait.until(EC.element_to_be_clickable((By.ID, "downloadExcelBtn")))
        download_button.click()
        
        # Wait for download to complete and rename
        taluka_name = LOGIN_TALUKA_MAP.get(username, username.replace("@", "_").replace(".", "_"))
        renamed_path = wait_for_download_and_rename(DOWNLOAD_DIR, taluka_name)
        
        if renamed_path:
            print(f"✅ Download and rename complete for {username}! File: {renamed_path}")
            return True
        else:
            print(f"❌ Failed to find or rename downloaded file for {username}.")
            return False
        
    except Exception as e:
        print(f"❌ Error occurred for {username}: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    finally:
        print("Closing browser...")
        driver.quit()


def concatenate_excel_files():
    """
    Find all .xlsx files in the downloads directory and merge them into a single file.
    """
    print("\n" + "=" * 60)
    print("CONCATENATING FILES")
    print("=" * 60)
    
    xlsx_files = glob.glob(os.path.join(DOWNLOAD_DIR, "*.csv"))
    
    # Filter out any existing combined file to avoid recursion if run multiple times
    xlsx_files = [f for f in xlsx_files if "combined_schedules" not in f]
    
    # Validation: Verify that there are at least some .xlsx files
    if len(xlsx_files) == 0:
        print(f"❌ Error: No Excel files found in {DOWNLOAD_DIR}.")
        return

    # Validation: Verify that none of them have "crdwonload" or "Schedule" in them
    forbidden_words = ["crdwonload", "Schedule"]
    files_with_forbidden_words = [f for f in xlsx_files if any(word in os.path.basename(f) for word in forbidden_words)]
    if files_with_forbidden_words:
        print("❌ Error: Some files have forbidden words in their filenames:")
        for f in files_with_forbidden_words:
            print(f"  - {os.path.basename(f)}")
        return

    print(f"Found {len(xlsx_files)} Excel files. All validations passed.")
    
    all_dfs = []
    for file in xlsx_files:
        try:
            print(f"Reading: {os.path.basename(file)}")
            try:
                df = pd.read_excel(file, engine='csv')
            except Exception:
                df = pd.read_csv(file, encoding='utf-8-sig')
            all_dfs.append(df)
        except Exception as e:
            print(f"Error reading {file}: {e}")
    
    if all_dfs:
        try:
            print("Merging files...")
            # Concatenate all dataframes
            merged_df = pd.concat(all_dfs, ignore_index=True)

            # Clean up string artifacts in all string columns
            for col in merged_df.select_dtypes(include='object').columns:
                merged_df[col] = (merged_df[col]
                    .str.strip('=')
                    .str.strip('"')
                    .str.replace(r'N\.A(?!\.)', 'N.A.', regex=True))

            # For every row where "block" and "village" are blank, use the Town mapping
            if all(col in merged_df.columns for col in ["block", "village", "town"]):
                # Map of Town to (Block, Village)
                town_map = {
                    "Ponda": {"block": "Ponda", "village": "Ponda"},
                    "Mapusa": {"block": "Bardez", "village": "Mapusa"},
                    "Pernem": {"block": "Pernem", "village": "Pernem"},
                    "Quepem": {"block": "Quepem", "village": "Quepem"},
                    "Margao": {"block": "Salcete", "village": "Margao"},
                    "Sanguem": {"block": "Sanguem", "village": "Sanguem"},
                    "Cuncolim": {"block": "Salcete", "village": "Cuncolim"},
                    "Bicholim": {"block": "Bicholim", "village": "Bicholim"},
                    "Canacona": {"block": "Canacona", "village": "Canacona"},
                    "Curchorem": {"block": "Quepem", "village": "Curchorem"},
                    "Mormugao": {"block": "Mormugao", "village": "Mormugao"},
                    "Curchorem Cacora": {"block": "Quepem", "village": "Cacora"},
                    "City Corporation Panaji": {"block": "Tiswadi", "village": "Panaji"},
                }
                
                mask = (merged_df['block'] == 'N.A.') & (merged_df['village'] == 'N.A.')
                
                for town, mapping in town_map.items():
                    town_mask = mask & (merged_df['town'] == town)
                    merged_df.loc[town_mask, 'block'] = mapping['block']
                    merged_df.loc[town_mask, 'village'] = mapping['village']
                
                # Fallback for towns not in the map
                remaining_mask = (merged_df['block'].isna() | (merged_df['block'] == '')) & \
                                (merged_df['village'].isna() | (merged_df['village'] == '')) & \
                                (~merged_df['town'].isna()) & (merged_df['town'] != '')
                
                merged_df.loc[remaining_mask, 'block'] = merged_df.loc[remaining_mask, 'town']
                merged_df.loc[remaining_mask, 'village'] = merged_df.loc[remaining_mask, 'town']
                
                print(f"Filled blanks in Block/Village using Town mapping for {mask.sum()} rows and fallback for {remaining_mask.sum()} rows.")
            
            # Sort by "Spring ID" column and remove duplicates
            if "spring_id" in merged_df.columns:
                print("Sorting by Spring ID and removing duplicates...")
                merged_df = merged_df.sort_values(by="spring_id")
                # Drop duplicates based on spring_id, keep the first occurrence
                merged_df = merged_df.drop_duplicates(subset=["spring_id"], keep='first')

            output_file = os.path.join(DOWNLOAD_DIR, "combined_schedules.csv")
            merged_df.to_csv(output_file, index=False)
            
            print(f"✅ Successfully created combined file: {output_file}")
            print(f"Total rows: {len(merged_df)}")
        except Exception as e:
            print(f"Error merging files: {e}")
    else:
        print("No valid data frames to merge.")


def download_all_schedules():
    """
    Iterate through all credentials and download schedules for each in parallel.
    """
    # Clear existing downloads only when starting a fresh download run
    if os.path.exists(DOWNLOAD_DIR):
        print(f"Clearing existing downloads folder: {DOWNLOAD_DIR}")
        shutil.rmtree(DOWNLOAD_DIR)
    os.makedirs(DOWNLOAD_DIR, exist_ok=True)

    print("=" * 60)
    print("Spring Census Schedules Downloader (Parallel)")
    print(f"Processing {len(CREDENTIALS)} account(s)")
    print("=" * 60)
    
    results = []
    
    def process_credential(cred):
        username = cred["username"]
        password = cred["password"]
        
        MAX_DOWNLOAD_RETRIES = 3
        for attempt in range(1, MAX_DOWNLOAD_RETRIES + 1):
            print(f"Starting process for: {username} (Attempt {attempt}/{MAX_DOWNLOAD_RETRIES})")
            success = download_schedules_for_user(username, password)
            if success:
                return {
                    "username": username,
                    "success": True
                }
            
            if attempt < MAX_DOWNLOAD_RETRIES:
                wait_time = 5 * attempt
                print(f"⚠️ Process failed for {username}. Retrying in {wait_time}s...")
                time.sleep(wait_time)
        
        return {
            "username": username,
            "success": False
        }

    # Use ThreadPoolExecutor for parallel execution
    # Adjust max_workers as needed; too many might overload the system or get rate-limited
    max_workers = min(5, len(CREDENTIALS))
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_cred = {executor.submit(process_credential, cred): cred for cred in CREDENTIALS}
        for future in concurrent.futures.as_completed(future_to_cred):
            try:
                result = future.result()
                results.append(result)
                status = "✅ Success" if result["success"] else "❌ Failed"
                print(f"Finished: {result['username']} - {status}")
            except Exception as exc:
                cred = future_to_cred[future]
                print(f"Credential {cred['username']} generated an exception: {exc}")
                results.append({
                    "username": cred["username"],
                    "success": False
                })
    
    # Print summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    successful = sum(1 for r in results if r["success"])
    failed = len(results) - successful
    
    print(f"Total accounts processed: {len(results)}")
    print(f"✅ Successful: {successful}")
    print(f"❌ Failed: {failed}")
    
    if failed > 0:
        print("\nFailed accounts:")
        for r in results:
            if not r["success"]:
                print(f"  - {r['username']}")

if __name__ == "__main__":
    start_time = datetime.datetime.now()
    print(f"Script started at: {start_time.strftime('%Y-%m-%d %H:%M:%S')}")

    if ANTI_CAPTCHA_API_KEY == "YOUR_API_KEY_HERE":
        print("\nERROR: Please set your anti-captcha.com API key in the script!")
        print("Get your API key from: https://anti-captcha.com/clients/settings/apisetup")
        exit(1)
    
    download_all_schedules()
    # Concatenate all downloaded Excel files
    concatenate_excel_files()

    end_time = datetime.datetime.now()
    duration = end_time - start_time
    print(f"\nScript finished at: {end_time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Total duration: {duration}")
