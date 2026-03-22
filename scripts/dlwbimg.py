#!/usr/bin/env python3
import os
import time
import json
import requests
import pandas as pd
import urllib3
import urllib.parse
import subprocess
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException


urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Configuration
def load_env():
    if os.path.exists(".env"):
        with open(".env") as f:
            for line in f:
                if line.strip() and not line.startswith("#"):
                    key, value = line.strip().split("=", 1)
                    os.environ[key] = value

load_env()
INPUT_FILE = os.getenv("WB_INPUT_FILE")
TARGET_FOLDER = os.getenv("WB_TARGET_FOLDER")
LOGIN_URL = os.getenv("WB_LOGIN_URL")
ANTI_CAPTCHA_API_KEY = os.getenv("ANTI_CAPTCHA_API_KEY")
CREDENTIALS_STR = os.getenv("CREDENTIALSWB", "[]")
CREDENTIALS = json.loads(CREDENTIALS_STR[1:-1])

def solve_captcha(image_base64):
    url = "https://api.anti-captcha.com/createTask"
    data = {
        "clientKey": ANTI_CAPTCHA_API_KEY,
        "task": {
            "type": "ImageToTextTask",
            "body": image_base64
        }
    }
    resp = requests.post(url, json=data, verify=False).json()
    if resp.get("errorId") != 0:
        raise Exception(f"Anti-captcha error: {resp.get('errorDescription')}")
    
    task_id = resp.get("taskId")
    for _ in range(30):
        time.sleep(2)
        res = requests.post("https://api.anti-captcha.com/getTaskResult", 
                            json={"clientKey": ANTI_CAPTCHA_API_KEY, "taskId": task_id}, verify=False).json()
        if res.get("status") == "ready":
            return res.get("solution", {}).get("text")
    raise Exception("Captcha timeout")

def get_existing_images(folder):
    existing = set()
    print(f"Scanning {folder} for existing images...")
    for root, _, files in os.walk(folder):
        for f in files:
            if f.lower().endswith(('.jpg', '.jpeg', '.png', '.gif')):
                existing.add(f.lower())
    return existing

def login_and_get_session():
    chrome_options = Options()
#     chrome_options.add_argument("--headless")
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.page_load_strategy = 'eager'
    driver = webdriver.Chrome(options=chrome_options)
    driver.set_page_load_timeout(60)
    
    try:
        driver.get(LOGIN_URL)
        wait = WebDriverWait(driver, 30)
        
        # Try credentials until success
        logged_in = False
        for creds in CREDENTIALS:
            try:
                print("Filling in credentials...")
                username_field = wait.until(EC.presence_of_element_located((By.ID, "username")))
                username_field.clear()
                username_field.send_keys(creds["username"])

                password_field = driver.find_element(By.ID, "password")
                password_field.clear()
                password_field.send_keys(creds["password"])

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
                
                captcha_text = solve_captcha(captcha_base64)
                driver.find_element(By.ID, "captcha").clear()
                driver.find_element(By.ID, "captcha").send_keys(captcha_text)
                driver.find_element(By.CSS_SELECTOR, "button.loginBtn").click()
                
                try:
                    wait.until(lambda d: "login" not in d.current_url.lower())
                except TimeoutException:
                    pass

                if "login" not in driver.current_url.lower():
                    print(f"Logged in as {creds['username']}")
                    logged_in = True
                    break
                else:
                    print(f"Login failed for {creds['username']}, trying next...")
                    driver.get(LOGIN_URL) # Refresh for next attempt
            except Exception as e:
                print(f"Error with {creds['username']}: {e}")
                driver.get(LOGIN_URL)
        
        if not logged_in:
            raise Exception("All login attempts failed")
        
        cookies = driver.get_cookies()
        session = requests.Session()
        session.verify = False
        for cookie in cookies:
            session.cookies.set(cookie['name'], cookie['value'])
        return session
    finally:
        driver.quit()

def cleanup_text_files(folder):
    print(f"Cleaning up text files in {folder}...")
    for root, _, files in os.walk(folder):
        for f in files:
            filepath = os.path.join(root, f)
            try:
                mime_type = subprocess.check_output(['file', '--mime-type', '-b', filepath]).decode('utf-8').strip()
                if mime_type.startswith('text/'):
                    print(f"Removing text file: {filepath} (mimetype: {mime_type})")
                    os.remove(filepath)
            except Exception as e:
                print(f"Error checking {filepath}: {e}")

def delete_extra_images(folder, expected_filenames):
    print(f"Deleting extra images in {folder}...")
    expected_filenames_lower = {f.lower() for f in expected_filenames}
    for root, _, files in os.walk(folder):
        for f in files:
            if f.lower().endswith(('.jpg', '.jpeg', '.png', '.gif')):
                if f.lower() not in expected_filenames_lower:
                    filepath = os.path.join(root, f)
                    print(f"Removing extra image: {filepath}")
                    try:
                        os.remove(filepath)
                    except Exception as e:
                        print(f"Error removing {filepath}: {e}")

def main():

    cleanup_text_files(TARGET_FOLDER)

    # Read local CSV file
    print(f"Reading local file: {INPUT_FILE}...")
    try:
        df = pd.read_csv(INPUT_FILE)
    except FileNotFoundError:
        print(f"Error: The file {INPUT_FILE} was not found.")
        return
    except pd.errors.EmptyDataError:
        print(f"Error: The file {INPUT_FILE} is empty.")
        return
    
    image_cols = ["image_path"]
    # Pattern for Water Body images: LOGIN_URL + "/admin/file/552/images/"
    # Since LOGIN_URL might already have /micensus, we need to be careful
    base_img_url = "https://wrcensus.mowr.gov.in/micensus/common/images/waterbody-"

    all_image_urls = []
    for col in image_cols:
        if col in df.columns:
            for val in df[col].dropna().tolist():
                all_image_urls.append(base_img_url + val)

    print(f"Found {len(all_image_urls)} image URLs in sheet.")
    
    existing_images = get_existing_images(TARGET_FOLDER)
    print(f"Found {len(existing_images)} existing images in {TARGET_FOLDER}.")
    
    to_download = []
    expected_filenames = []
    for url in all_image_urls:
        filename = os.path.basename(urllib.parse.urlparse(url).path)
        expected_filenames.append(filename)
        if filename.lower() not in existing_images:
            to_download.append((url, filename))

    delete_extra_images(TARGET_FOLDER, expected_filenames)

    print(f"Images to download: {len(to_download)}")
    
    if not to_download:
        print("No new images to download.")
        return

    session = login_and_get_session()
    print("Logged in successfully.")
    
    os.makedirs(TARGET_FOLDER, exist_ok=True)
    
    # Save images to a subfolder to avoid cluttering or if user specifically wants them there.
    # But issue says "directly into the folder"
    
    # It might be safer to save into a specific subfolder if they are thousands.
    # I'll stick to what the user said: "directly into the folder"
    
    for i, (url, filename) in enumerate(to_download):
        print(f"[{i+1}/{len(to_download)}] Downloading {filename}...")
        try:
            r = session.get(url, stream=True, verify=False)
            if r.status_code == 200:
                with open(os.path.join(TARGET_FOLDER, filename), 'wb') as f:
                    for chunk in r.iter_content(chunk_size=8192):
                        f.write(chunk)
            else:
                print(f"Failed to download {filename}: HTTP {r.status_code}")
        except Exception as e:
            print(f"Error downloading {filename}: {e}")

if __name__ == "__main__":
    main()
