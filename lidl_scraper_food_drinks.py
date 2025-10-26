import os
import json
import time 
import re 
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException, ElementClickInterceptedException
from bs4 import BeautifulSoup

# --- CONFIGURATION ---
URL = "https://www.lidl.at/c/essen-trinken/s10068374"
INPUT_JSON_PATH = "input_scraped_data.json" # Target output file for the categorizer
WAIT_TIME_SECONDS = 15

# --- SELECTORS ---
PRODUCT_CARD_SELECTOR = 'div.odsc-tile.product-grid-box' 
INNER_CONTAINER_SELECTOR = 'div.odsc-tile__inner' 
LOAD_MORE_BUTTON_SELECTOR = 'button.s-load-more__button'
LOAD_MORE_PROGRESS_SELECTOR = 'div.s-load-more__text'
COOKIE_ACCEPT_ID = "onetrust-accept-btn-handler" 

# --- HEADLESS CHROME OPTIONS ---
options = webdriver.ChromeOptions()
# You can uncomment the line below to run headless when you deploy this script
# options.add_argument('--headless=new') 
options.add_argument('--no-sandbox')
options.add_argument('--disable-dev-shm-usage')
options.add_argument('--window-size=1920,1080')
options.add_argument('user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36')
options.add_experimental_option("excludeSwitches", ["enable-automation"]) 
options.add_experimental_option('useAutomationExtension', False)
options.add_argument('--disable-gpu')
options.add_argument('--disable-logging')
options.add_argument('--log-level=3') 


def get_current_counts(driver):
    """Parses the progress element to get displayed and total product counts."""
    try:
        progress_element = driver.find_element(By.CSS_SELECTOR, LOAD_MORE_PROGRESS_SELECTOR)
        text = progress_element.text
        match = re.search(r'(\d+)\s*/\s*(\d+)', text)
        if match:
            displayed = int(match.group(1))
            total = int(match.group(2))
            return displayed, total
        return 0, 0
    except NoSuchElementException:
        return -1, -1 


def scrape_lidl_html(url):
    """
    Scrapes all product data from the Lidl category page, filtering exclusively 
    for in-store promotional items and extracting only the date range.
    """
    driver = None
    try:
        # Use ChromeDriverManager to manage the driver executable
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=options)
    except Exception as e:
        print(f"Error initializing WebDriver: {e}")
        return []

    print(f"Navigating to {url}...")
    driver.get(url)
    
    # --- 1. HANDLE COOKIE BANNER (ZUSTIMMEN) ---
    try:
        WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.ID, COOKIE_ACCEPT_ID))
        ).click()
        print("Cookie banner accepted ('ZUSTIMMEN').")
        time.sleep(1) 
    except TimeoutException:
        print("No cookie banner found or timed out.")
        pass

    # --- 2. INITIAL LOAD WAIT ---
    print("Starting product loading loop...")
    
    try:
        WebDriverWait(driver, WAIT_TIME_SECONDS).until(
            lambda d: len(d.find_elements(By.CSS_SELECTOR, PRODUCT_CARD_SELECTOR)) >= 12
        )
        print("Initial 12 products loaded.")
    except TimeoutException:
        final_count = len(driver.find_elements(By.CSS_SELECTOR, PRODUCT_CARD_SELECTOR))
        print(f"Timeout waiting for 12 products. Found only {final_count}. Proceeding.")

    # --- 3. LOAD ALL PRODUCTS LOOP (Pagination) ---
    max_clicks = 20 
    clicks = 0
    while clicks < max_clicks:
        
        initial_count = len(driver.find_elements(By.CSS_SELECTOR, PRODUCT_CARD_SELECTOR))
        displayed, total = get_current_counts(driver)
        
        if displayed == -1 or initial_count >= total:
            print(f"All {initial_count} products loaded or end of list reached.")
            break
        
        print(f"Currently displayed: {displayed} / {total}. Clicking 'Load More' (Click {clicks + 1})...")
        
        try:
            load_more_button = driver.find_element(By.CSS_SELECTOR, LOAD_MORE_BUTTON_SELECTOR)
            
            # 3a. SCROLL TO THE BUTTON TO ENSURE IT'S IN VIEW FOR THE CLICK
            driver.execute_script("arguments[0].scrollIntoView(false);", load_more_button)
            
            # 3b. CLICK
            WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, LOAD_MORE_BUTTON_SELECTOR))
            ).click()
            
            # 3c. SYNCHRONIZATION: Wait for the number of product cards to increase
            WebDriverWait(driver, 15).until(
                lambda d: len(d.find_elements(By.CSS_SELECTOR, PRODUCT_CARD_SELECTOR)) > initial_count
            )
            new_count = len(driver.find_elements(By.CSS_SELECTOR, PRODUCT_CARD_SELECTOR))
            print(f"New batch loaded. New count: {new_count}")

            # --- POST-LOAD SCROLL: Scroll to the last *previously loaded* element ---
            product_cards = driver.find_elements(By.CSS_SELECTOR, PRODUCT_CARD_SELECTOR)
            if len(product_cards) >= initial_count:
                last_old_element = product_cards[initial_count - 1]
                driver.execute_script("arguments[0].scrollIntoView(false);", last_old_element)
                time.sleep(1) 
                print(f"Scrolled to last product before new batch (index {initial_count - 1}) to ensure rendering.")
            
            clicks += 1
            
        except TimeoutException:
            print("Timeout waiting for new products to load after click. Assuming end of list/failure.")
            break
        except (NoSuchElementException, ElementClickInterceptedException):
            print("Load More button not found or not clickable. Assuming end of list.")
            break
            
    # --- 4. FINAL SCRAPE AND PARSE (Filter In-Store Items) ---
    scraped_data = []
    try:
        print("\nStarting final HTML parsing with BeautifulSoup...")
        html_content = driver.page_source
        soup = BeautifulSoup(html_content, 'html.parser')

        product_cards = soup.select(PRODUCT_CARD_SELECTOR)
        
        for card in product_cards:
            inner_container = card.select_one(INNER_CONTAINER_SELECTOR)
            if not inner_container:
                continue 
            
            # --- Availability Status & Filtering ---
            availability_container = card.select_one('.product-grid-box__availabilities')
            
            if availability_container:
                status_label = availability_container.select_one('.ods-badge__label')
                if status_label:
                    status_text = status_label.text.strip() # e.g., "in der Filiale 20.10. - 22.10."
                    
                    # Only proceed if the item is explicitly marked "in der Filiale"
                    if "in der Filiale" in status_text:
                        # Extract only the date range
                        availability_status = status_text.replace("in der Filiale", "").strip()

                        # --- NAME and URL ---
                        title_tag = card.select_one('a.odsc-tile__link')
                        name = title_tag.text.strip() if title_tag else "N/A"
                        relative_url = title_tag.get('href') if title_tag and title_tag.get('href') else ""
                        clean_path = relative_url.split('#')[0] if '#' in relative_url else relative_url
                        full_url = "https://www.lidl.at" + clean_path
    
                        # --- PRICE and UNIT parsing ---
                        current_price_tag = inner_container.select_one('.ods-price__value')
                        current_price_val = current_price_tag.text.strip().replace('€', '').replace('*', '').replace('-', '0') if current_price_tag else "N/A"
                        
                        old_price_tag = inner_container.select_one('.ods-price__stroke-price s')
                        old_price_val = old_price_tag.text.strip().replace('€', '') if old_price_tag else "N/A"
                        
                        unit_tag = inner_container.select_one('.ods-price__footer')
                        unit_val = unit_tag.text.strip().replace('\n', ' ').replace('Je ', '').replace('<br>', '').strip() if unit_tag else ""
    
                        # --- OUTPUT DICT (Keys adjusted to match the categorizer's expected input) ---
                        product_info = {
                            "Name": name, 
                            "Price": f"€{current_price_val.strip()}", # Re-add € for consistency
                            "Old Price": f"€{old_price_val.strip()}" if old_price_val != "N/A" else "€N/A",
                            "Unit": unit_val, 
                            "URL": full_url,
                            "Availability (Date Range)": availability_status
                        }
                        scraped_data.append(product_info)

        print(f"\nSuccessfully parsed and filtered {len(scraped_data)} in-store promotional products.")
        
        return scraped_data

    except Exception as e:
        print(f"\nAn error occurred during final parsing: {e}")
        return []
    finally:
        if driver:
            driver.quit()
            print("\nWebDriver closed.")


if __name__ == "__main__":
    
    # 1. Run the scraper
    all_products = scrape_lidl_html(URL)
    
    # 2. Save the data to the expected JSON file
    if all_products:
        try:
            with open(INPUT_JSON_PATH, 'w', encoding='utf-8') as f:
                json.dump(all_products, f, ensure_ascii=False, indent=2)
            print(f"\nSUCCESS: Scraped data saved to '{INPUT_JSON_PATH}'.")
            print("You can now run 'python categorizer.py' to classify the data.")
        except Exception as e:
            print(f"ERROR: Could not save data to JSON file: {e}")
    else:
        print("\nNo products were scraped; skipping JSON save.")
