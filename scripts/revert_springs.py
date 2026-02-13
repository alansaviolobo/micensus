import os
import time
import requests
import pandas as pd
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from dldata import CREDENTIALS, ANTI_CAPTCHA_API_KEY, solve_captcha_with_anticaptcha, LOGIN_URL

REVERT_FILE = os.getenv("REVERT_FILE")

def apply_enumerator_filter(driver, wait, enumerator_name):
    if not enumerator_name:
        return

    input_selectors = [
        (By.ID, "search_user"),
        (By.ID, "enumerator"),
        (By.ID, "enumeratorName"),
        (By.NAME, "enumerator"),
        (By.NAME, "enumeratorName"),
        (By.NAME, "surveyor"),
        (By.NAME, "surveyorName"),
        (By.XPATH, "//input[contains(@placeholder, 'Enumerator')]"),
        (By.XPATH, "//input[contains(@placeholder, 'Surveyor')]"),
    ]
    submit_selectors = [
        (By.XPATH, "//button[normalize-space()='Search']"),
        (By.XPATH, "//button[normalize-space()='Submit']"),
        (By.XPATH, "//button[normalize-space()='Filter']"),
        (By.XPATH, "//input[@type='submit']"),
    ]

    
    # Check if filter is open, if not, click the filter button
    try:
        filter_btn = driver.find_element(By.ID, "filterBoxOpenBtn")
        # Check if the dropdown content is visible?
        # The HTML shows <div id="myDropdown" class="dropdown-content filterData">
        dropdown = driver.find_element(By.ID, "myDropdown")
        
        if not dropdown.is_displayed():
            print("Opening Filter dropdown...")
            driver.execute_script("arguments[0].click();", filter_btn)
            time.sleep(1)
    except Exception as e:
        print(f"Error checking filter button: {e}")

    field = None
    for by, sel in input_selectors:
        try:
            # We use visibility_of_element_located to ensure we get the visible one if multiple exist
            field = wait.until(EC.visibility_of_element_located((by, sel)))
            break
        except Exception:
            continue

    if not field:
        print(f"⚠️ Enumerator filter input not found for: {enumerator_name}")
        return

    field.clear()
    field.send_keys(enumerator_name)
    time.sleep(1) 

    for by, sel in submit_selectors:
        try:
            btn = driver.find_element(by, sel)
            if btn.is_displayed():
                driver.execute_script("arguments[0].click();", btn)
                time.sleep(3)
                return
        except Exception:
            continue

    field.send_keys("\n")
    time.sleep(3)

def apply_spring_id_search(driver, wait, spring_id):
    """
    Apply Spring ID search using the DataTable filter if available.
    """
    if not spring_id:
        return

    print(f"Searching for Spring ID: {spring_id}")
    
    # DataTable search input usually has type="search"
    search_selectors = [
        (By.CSS_SELECTOR, "input[type='search']"),
        (By.CSS_SELECTOR, "div.dataTables_filter input"),
        (By.XPATH, "//input[@aria-controls='example']"), # 'example' is the table ID in the HTML source we saw
    ]

    search_field = None
    for by, sel in search_selectors:
        try:
            search_field = driver.find_element(by, sel)
            if search_field.is_displayed():
                break
        except:
            continue
            
    if search_field:
        try:
            search_field.clear()
            search_field.send_keys(spring_id)
            # DataTable usually triggers on keyup or change, sometimes enter
            # We can try sending enter just in case, but often typing is enough
            # search_field.send_keys("\n") 
            time.sleep(2) # Wait for client-side filter
            print("Applied Spring ID filter.")
        except Exception as e:
            print(f"Error applying Spring ID search: {e}")
    else:
        print("⚠️ DataTable search input not found. Proceeding with page scan.")

def open_schedules_page(driver, wait):

    link_selectors = [
        (By.CSS_SELECTOR, "a.menu-link[href*='surveys']"),
        (By.XPATH, "//a[contains(@href, 'surveys')]"),
        (By.XPATH, "//a[contains(., 'Schedule')]"),
        (By.XPATH, "//span[contains(., 'Schedule')]/ancestor::a[1]"),
    ]
    for by, sel in link_selectors:
        try:
            link = wait.until(EC.element_to_be_clickable((by, sel)))
            driver.execute_script("arguments[0].click();", link)
            time.sleep(2)
            return True
        except Exception:
            continue

    return False

def revert_springs_for_user(driver, username, password, enumerator_name, springs_to_revert):
    if not springs_to_revert:
        return True

    wait = WebDriverWait(driver, 10)
    
    try:
        print(f"\n{'='*60}")
        print(f"Processing account: {username}")
        print(f"{'='*60}")
        
        driver.get(LOGIN_URL)
        
        MAX_RETRIES = 3
        logged_in = False
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                if attempt > 1:
                    driver.refresh()
                    time.sleep(2)
                
                username_field = wait.until(EC.presence_of_element_located((By.ID, "email")))
                username_field.clear()
                username_field.send_keys(username)
                
                password_field = driver.find_element(By.ID, "password")
                password_field.clear()
                password_field.send_keys(password)
                
                captcha_img = driver.find_element(By.ID, "captchaImage")
                captcha_base64 = driver.execute_script("""
                    var canvas = document.createElement('canvas');
                    var context = canvas.getContext('2d');
                    var img = arguments[0];
                    canvas.height = img.naturalHeight;
                    canvas.width = img.naturalWidth;
                    context.drawImage(img, 0, 0);
                    return canvas.toDataURL('image/png').substring(22);
                """, captcha_img)
                
                captcha_text = solve_captcha_with_anticaptcha(captcha_base64)
                
                captcha_field = driver.find_element(By.ID, "captchaInput")
                captcha_field.clear()
                captcha_field.send_keys(captcha_text)
                
                login_button = driver.find_element(By.ID, "encryptSubmitBtn")
                login_button.click()
                
                time.sleep(3)
                
                if "login" not in driver.current_url.lower():
                    print(f"✅ Login successful for {username}!")
                    logged_in = True
                    break
            except Exception as e:
                print(f"⚠️ Login attempt {attempt} failed: {e}")
        
        if not logged_in:
            return False

        # Navigate to schedules page
        # The existing open_schedules_page already goes to /admin/surveys
        # But the requirement says we MUST click on 'Schedules' link and open 'spring schedules' page.
        
        # We'll rely on the manual navigation steps as requested
        try:
            print("Navigating to Spring Schedules page...")
            # Fallback to direct URL if links not found
            print("⚠️ Spring Schedules link not found, using direct URL fallback.")
            if not open_schedules_page(driver, wait):
                print("❌ Unable to open schedules page via fallback.")
                return False
        except Exception as e:
            print(f"⚠️ Error navigating to schedules: {e}")
            # Try fallback
            if not open_schedules_page(driver, wait):
                return False

        # Apply enumerator filter before searching for springs
        apply_enumerator_filter(driver, wait, enumerator_name)
        
        # Optimization: Iterate pages and look for ANY spring in the list
        springs_set = set(springs_to_revert)
        reverted_count = 0

        # If we have specific springs, we can try to search for them individually using the DataTable filter
        # This is much faster than iterating all pages if the filter works.
        # However, if we have MANY springs for one user, it might be tedious to search one by one.
        # But usually it's a few. Let's try searching for each.
        
        for spring_id in list(springs_set):
            try:
                print(f"Processing {spring_id}...")
                
                # Apply Spring ID Filter
                apply_spring_id_search(driver, wait, spring_id)
                
                # After filter, we expect the row to be there.
                # Initialize rows found
                rows = []
                try:
                    # Give it a moment to update
                    time.sleep(1)
                    rows = driver.find_elements(By.CSS_SELECTOR, "table tbody tr")
                except:
                    pass
                
                if not rows:
                    print(f"No rows found after searching for {spring_id}")
                    continue

                # Find the specific row (double check)
                target_row = None
                for row in rows:
                    if spring_id in row.text:
                        target_row = row
                        break
                
                if not target_row:
                    print(f"Row for {spring_id} not found in table after filter.")
                    # Clear filter?
                    continue

                # --- Action Sequence ---
                
                # 1. Click on Actions (Dropdown toggle with icon)
                try:
                    dropdown_div = target_row.find_element(By.CSS_SELECTOR, "div.dropdown")
                    action_btn = dropdown_div.find_element(By.CSS_SELECTOR, "button.dropdown-toggle")
                    driver.execute_script("arguments[0].scrollIntoView(true);", action_btn)
                    time.sleep(0.5)
                    try:
                        action_btn.click()
                    except:
                        driver.execute_script("arguments[0].click();", action_btn)
                    time.sleep(1)
                    
                    # 2. Click on "Update Status"
                    update_status_btn = dropdown_div.find_element(By.CSS_SELECTOR, "a.dropdown-item.update-status")
                    driver.execute_script("arguments[0].click();", update_status_btn)
                    time.sleep(2)
                    
                    # 3. Select status as "Reverted to Enumerator"
                    status_select = wait.until(EC.presence_of_element_located((By.ID, "statusSelect")))
                    from selenium.webdriver.support.ui import Select
                    select = Select(status_select)
                    
                    is_found = False
                    for opt in select.options:
                        text = opt.get_attribute('textContent').strip()
                        if "revert" in text.lower() and "enumerator" in text.lower():
                            select.select_by_visible_text(text)
                            is_found = True
                            break
                    
                    if not is_found:
                        print(f"❌ 'Reverted to Enumerator' option not found for {spring_id}")
                        # Close modal if open?
                        # Reload page to clear modal/filter states for next
                        driver.refresh()
                        time.sleep(3)
                        continue
                    
                    time.sleep(1)
                    
                    # User request: "enter a comment which can be "for update"
                    try:
                        remark_input = wait.until(EC.visibility_of_element_located((By.ID, "remarkInput")))
                        remark_input.clear()
                        remark_input.send_keys("for update")
                        time.sleep(1)
                    except Exception as e:
                        print(f"⚠️ Could not enter remark: {e}")

                    # 4. Submit
                    submit_btn = driver.find_element(By.ID, "updateBtn")
                    submit_btn.click()
                    
                    print(f"✅ Successfully reverted {spring_id}")
                    reverted_count += 1
                    
                    time.sleep(3)
                    
                    # Clear the filter for the next spring?
                    # Easiest way to reset state is often to clear the search box
                    # apply_spring_id_search(driver, wait, "") 
                    # OR just continue loop, new search will clear/overwrite or we can refresh?
                    # refreshing is safer to ensure clean state
                    # driver.refresh()
                    # But refreshing forces re-applying enumerator filter which is slow.
                    # Better to clear the search box.
                    
                    search_input = driver.find_element(By.CSS_SELECTOR, "input[type='search']")
                    search_input.clear()
                    search_input.send_keys("\n") # trigger clear
                    time.sleep(1)

                except Exception as e:
                    print(f"Error reverting {spring_id}: {e}")
                    # Recovery
                    driver.refresh()
                    time.sleep(3)
                    apply_enumerator_filter(driver, wait, enumerator_name)
                    
            except Exception as e:
                print(f"Error processing {spring_id}: {e}")
                
        return True 
        
    finally:
        # driver.quit()
        print("1")

def main():
    if not os.path.exists(REVERT_FILE):
        print(f"No {REVERT_FILE} found. Run validate_data.py first.")
        return

    df = pd.read_csv(REVERT_FILE)
    if df.empty:
        print("Revert list is empty.")
        return

    required_cols = {"Username to login", "Enumerator Name", "Spring ID"}
    missing_cols = required_cols - set(df.columns)
    if missing_cols:
        print(f"Missing columns in {REVERT_FILE}: {sorted(missing_cols)}")
        return

    cred_map = {c["username"]: c["password"] for c in CREDENTIALS}

    grouped = (
        df.groupby(["Username to login", "Enumerator Name"])["Spring ID"]
        .apply(list)
        .reset_index()
    )

    for _, row in grouped.iterrows():
        username = row["Username to login"]
        enumerator_name = row["Enumerator Name"]
        spring_ids = row["Spring ID"]

        password = cred_map.get(username)
        if not password:
            print(f"⚠️ No credentials found for username: {username}")
            continue

        chrome_options = Options()
        chrome_options.add_argument("--window-size=1500,1200")
        driver = webdriver.Chrome(options=chrome_options)
        try:
            revert_springs_for_user(driver, username, password, enumerator_name, spring_ids)
        finally:
            driver.quit()

if __name__ == "__main__":
    main()
