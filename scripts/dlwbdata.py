#!/usr/bin/env python3
"""
Script to automate login to wrcensus.mowr.gov.in/micensus/ and download Excel file.
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
LOGIN_URL = os.getenv("WB_LOGIN_URL", "https://wrcensus.mowr.gov.in/micensus/")
ANTI_CAPTCHA_API_KEY = os.getenv("ANTI_CAPTCHA_API_KEY")
DOWNLOAD_DIR = os.path.join(os.getcwd(), "downloads")
CREDENTIALS_STR = os.getenv("CREDENTIALSWB", "[]")
CREDENTIALS = json.loads(CREDENTIALS_STR[1:-1])

LINK_MAP = {
    "groundWaterScheme": "https://wrcensus.mowr.gov.in/micensus/groundWaterSchedule/ground-water-schedule-modification-list",
    "surfaceWaterScheme": "https://wrcensus.mowr.gov.in/micensus/surfaceWaterSchedule/surface-water-modification-list",
    "waterBodySchedule": "https://wrcensus.mowr.gov.in/micensus/waterBody/water-body-list",
}
         
# Taluka to login username mapping
TALUKA_LOGIN_MAP = {
    "Bardez": "S30D551B005929U01",
    "Bicholim": "S30D551B005930U01",
    "BicholimCity": "S30D551T252075U01",
    "Canacona": "S30D552B005935U01",
    "CanaconaCity": "S30D552T252100U01",
    "CuncolimCity": "S30D552T252095U01",
    "CurchoremCity": "S30D552T252096U01",
    "Dharbandora": "S30D552B006841U01",
    "MapusaCity": "S30D551T252061U01",
    "MargaoCity": "S30D552T252087U01",
    "Mormugao": "S30D552B005936U01",
    "PanajiCity": "S30D551T252071U01",
    "Pernem": "S30D551B005931U01",
    "PernemCity": "S30D551T252057U01",
    "Ponda": "S30D552B005932U01",
    "PondaCity": "S30D552T252082U01",
    "Quepem": "S30D552B005937U01",
    "QuepemCity": "S30D552T252097U01",
    "Salcete": "S30D552B005938U01",
    "Sanguem": "S30D552B005939U01",
    "SanguemCity": "S30D552T252099U01",
    "SankhaliCity": "S30D551T252077U01",
    "Sattari": "S30D551B005933U01",
    "Tiswadi": "S30D551B005934U01",
    "ValpoiCity": "S30D551T252079U01",
    "VascoCity": "S30D552T252084U01",
}

# Inverse map for easy lookup
LOGIN_TALUKA_MAP = {v: k for k, v in TALUKA_LOGIN_MAP.items()}

# Create directory if it doesn't exist (but don't clear it yet)
os.makedirs(DOWNLOAD_DIR, exist_ok=True)
print(f"Download directory ready: {DOWNLOAD_DIR}\n")


def wait_for_download_and_rename(download_dir, taluka_name, orig_filename, suffix, timeout=60):
    """
    Wait for a new .xlsx file to appear in the download directory and rename it.
    """
    print(f"Waiting for download to complete for {taluka_name}...")
    start_time = time.time()
    
    while time.time() - start_time < timeout:
        # Look for .xlsx files
        xlsx_files = glob.glob(os.path.join(download_dir, f"{orig_filename}*.csv"))
        
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
                    if current_size == last_size:
                        break
                    last_size = current_size
                    time.sleep(1)
                
                # Rename the file
                new_path = os.path.join(download_dir, f"{taluka_name}-{suffix}.csv")
                try:
                    if os.path.exists(new_path):
                        os.remove(new_path)
                    os.rename(newest_file, new_path)
                    print(f"✅ Renamed {os.path.basename(newest_file)} to {taluka_name}-{suffix}.csv")
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
    """
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
    
    get_result_url = "https://api.anti-captcha.com/getTaskResult"
    for _ in range(30):
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
    Login and download data Excel file for a specific user.
    """
    chrome_options = Options()
    chrome_options.add_argument("--window-size=2240,1440")
    # chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.page_load_strategy = 'eager'
    chrome_options.add_experimental_option("prefs", {
        "download.default_directory": DOWNLOAD_DIR,
        "download.prompt_for_download": False,
        "download.directory_upgrade": True,
        "safebrowsing.enabled": True
    })

    driver = webdriver.Chrome(options=chrome_options)
    driver.set_page_load_timeout(60)
    
    try:
        print(f"\n{'='*60}")
        print(f"Processing account: {username}")
        print(f"{'='*60}")
        
        print(f"Navigating to {LOGIN_URL}...")
        driver.get(LOGIN_URL)
        
        wait = WebDriverWait(driver, 10)
        
        MAX_RETRIES = 3
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                print(f"Login attempt {attempt}/{MAX_RETRIES}...")
                
                if attempt > 1:
                    print("Refreshing page for retry...")
                    driver.refresh()
                    time.sleep(2)
                
                print("Filling in credentials...")
                username_field = wait.until(EC.presence_of_element_located((By.ID, "username")))
                username_field.clear()
                username_field.send_keys(username)
                
                password_field = driver.find_element(By.ID, "password")
                password_field.clear()
                password_field.send_keys(password)
                
                print("Retrieving captcha image...")
                captcha_img = driver.find_element(By.ID, "refresh-image")
                
                captcha_base64 = driver.execute_script("""
                    var canvas = document.createElement('canvas');
                    var context = canvas.getContext('2d');
                    var img = arguments[0];
                    canvas.height = img.naturalHeight;
                    canvas.width = img.naturalWidth;
                    context.drawImage(img, 0, 0);
                    return canvas.toDataURL('image/png').substring(22);
                """, captcha_img)
                
                print("Solving captcha...")
                captcha_text = solve_captcha_with_anticaptcha(captcha_base64)
                
                captcha_field = driver.find_element(By.ID, "captcha")
                captcha_field.clear()
                captcha_field.send_keys(captcha_text)
                
                print("Submitting login form...")
                login_button = driver.find_element(By.CSS_SELECTOR, "button.loginBtn")
                login_button.click()
                
                time.sleep(3)
                
                if "login" not in driver.current_url.lower():
                    print(f"✅ Login successful for {username}!")
                    break
                else:
                    print(f"⚠️ Login attempt {attempt} failed.")
                    if attempt == MAX_RETRIES:
                        print(f"❌ All login attempts failed for {username}.")
                        return False
            
            except Exception as e:
                print(f"⚠️ Error during login attempt {attempt}: {e}")
                if attempt == MAX_RETRIES:
                    return False
        
        time.sleep(2)
        
        # Loop through all links in LINK_MAP
        for suffix, url in LINK_MAP.items():
            print(f"Processing download for {suffix}...")
            # Redirect to the specific URL as requested
            print(f"Redirecting to {suffix} modification list...")
            driver.get(url)
            time.sleep(2)
            
            try:
                # Find and click PDF download button
                print(f"Clicking PDF download button for {suffix}...")
                pdf_button = wait.until(EC.element_to_be_clickable((By.ID, "downloadPdfBtn")))
                driver.execute_script("arguments[0].click();", pdf_button)

                # Check the privacy checkbox
                print("Accepting privacy terms...")
                privacy_checkbox = wait.until(EC.element_to_be_clickable((By.ID, "confirmCheckbox")))
                driver.execute_script("arguments[0].click();", privacy_checkbox)

                # Click the final download button in the modal
                print(f"Downloading PDF file for {suffix}...")
                download_button = wait.until(EC.element_to_be_clickable((By.ID, "confirmBtn")))
                driver.execute_script("arguments[0].click();", download_button)

                taluka_name = LOGIN_TALUKA_MAP.get(username, username.replace("@", "_").replace(".", "_"))
                renamed_path = wait_for_download_and_rename(DOWNLOAD_DIR, taluka_name, suffix, suffix)
                
                if renamed_path:
                    print(f"✅ Download and rename complete for {username} ({suffix})! File: {renamed_path}")
                else:
                    print(f"❌ Failed to find or rename downloaded file for {username} ({suffix}).")
            except Exception as e:
                print(f"⚠️ Error downloading {suffix} for {username}: {e}")
                # Continue with other suffixes even if one fails
                continue
        
        return True
        
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
    Find all .csv files in the downloads directory, group them by keywords,
    and merge them into 3 separate combined files, sorted by 'unique_id'.
    """
    print("\n" + "=" * 60)
    print("CONCATENATING CSV FILES")
    print("=" * 60)
    
    keywords = ["waterBodySchedule", "surfaceWaterScheme", "groundWaterScheme"]
    
    for keyword in keywords:
        print(f"\nProcessing keyword: {keyword}")
        
        # Look for .csv files containing the keyword
        csv_files = glob.glob(os.path.join(DOWNLOAD_DIR, f"*{keyword}*.csv"))
        
        # Filter out any existing combined file to avoid recursion
        csv_files = [f for f in csv_files if "combined_" not in os.path.basename(f)]
        
        if not csv_files:
            print(f"No CSV files found for keyword: {keyword}")
            continue

        all_dfs = []
        for file in csv_files:
            try:
                print(f"Reading: {os.path.basename(file)}")
                df = pd.read_csv(file)
                all_dfs.append(df)
            except Exception as e:
                print(f"Error reading {file}: {e}")
        
        if all_dfs:
            try:
                print(f"Merging files for {keyword}...")
                merged_df = pd.concat(all_dfs, ignore_index=True)
                
                # Fill blanks in Block/Village using Town mapping if columns exist
                if all(col in merged_df.columns for col in ["block", "village", "town"]):
                    town_map = {
                        "Ponda": {"Block": "Ponda", "Village": "Ponda"},
                        "Quepem": {"Block": "Quepem", "Village": "Quepem"},
                        "Vasco": {"Block": "Mormugao", "Village": "Vasco"},
                        "Mapusa": {"Block": "Bardez", "Village": "Mapusa"},
                        "Panaji": {"Block": "Tiswadi", "Village": "Panaji"},
                        "Margao": {"Block": "Salcete", "Village": "Margao"},
                        "Sanguem": {"Block": "Sanguem", "Village": "Sanguem"},
                        "Cuncolim": {"Block": "Salcete", "Village": "Cuncolim"},
                        "Curchorem": {"Block": "Quepem", "Village": "Curchorem"},
                        "Curchorem Cacora": {"Block": "Quepem", "Village": "Cacora"},
                    }
                    
                    mask = (merged_df['block'].isna() | (merged_df['block'] == '')) & \
                           (merged_df['village'].isna() | (merged_df['village'] == '')) & \
                           (merged_df['town'].isin(town_map.keys()))
                    
                    for town, mapping in town_map.items():
                        town_mask = mask & (merged_df['town'] == town)
                        merged_df.loc[town_mask, 'block'] = mapping['Block']
                        merged_df.loc[town_mask, 'village'] = mapping['Village']
                    
                    remaining_mask = (merged_df['block'].isna() | (merged_df['block'] == '')) & \
                                    (merged_df['village'].isna() | (merged_df['village'] == '')) & \
                                    (~merged_df['town'].isna()) & (merged_df['town'] != '')
                    
                    merged_df.loc[remaining_mask, 'block'] = merged_df.loc[remaining_mask, 'town']
                    merged_df.loc[remaining_mask, 'village'] = merged_df.loc[remaining_mask, 'town']
                    
                    print(f"Filled blanks in Block/Village using Town mapping for {mask.sum()} rows and fallback for {remaining_mask.sum()} rows.")
                
                # Sort by "unique_id" column if it exists
                if "unique_id" in merged_df.columns:
                    print(f"Sorting by unique_id for {keyword}...")
                    merged_df = merged_df.sort_values(by="unique_id")
                
                output_file = os.path.join(DOWNLOAD_DIR, f"combined_{keyword}.csv")
                merged_df.to_csv(output_file, index=False)
                
                print(f"✅ Successfully created combined file: {output_file}")
                print(f"Total rows: {len(merged_df)}")
            except Exception as e:
                print(f"Error merging files for {keyword}: {e}")
        else:
            print(f"No valid data frames to merge for {keyword}.")


def download_all_schedules():
    """
    Iterate through all credentials and download data for each in parallel.
    """
    if os.path.exists(DOWNLOAD_DIR):
        print(f"Clearing existing downloads folder: {DOWNLOAD_DIR}")
        shutil.rmtree(DOWNLOAD_DIR)
    os.makedirs(DOWNLOAD_DIR, exist_ok=True)

    print("=" * 60)
    print("MI Census Water Bodies Downloader (Parallel)")
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

    max_workers = 4
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

    if ANTI_CAPTCHA_API_KEY == "YOUR_API_KEY_HERE" or ANTI_CAPTCHA_API_KEY is None:
        print("\nERROR: Please set your anti-captcha.com API key in the script or .env!")
        print("Get your API key from: https://anti-captcha.com/clients/settings/apisetup")
        exit(1)
    
    download_all_schedules()
    concatenate_excel_files()

    end_time = datetime.datetime.now()
    duration = end_time - start_time
    print(f"\nScript finished at: {end_time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Total duration: {duration}")
