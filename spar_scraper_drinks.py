from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException, ElementClickInterceptedException, StaleElementReferenceException
from bs4 import BeautifulSoup
import time 
import re 

# --- Configuration ---
TARGET_ADDRESS = "Jägerstraße, 1200 Wien, Austria" # Location to set the store
BASE_URL = "https://www.spar.at/produktwelt/getraenke"
# We scrape products that are 'on offer' by requesting the first page with the filter
URL = f"{BASE_URL}?inAngebot=true&page=1"
WAIT_TIME_SECONDS = 15

# --- General Selectors ---
PRODUCT_GRID_ID = "spar-plp__grid" 
PRODUCT_CARD_SELECTOR = 'div.spar-plp__grid-item article.product-tile' 
PAGINATION_TEXT_SELECTOR = '.pagination__text' 

# --- Location Setting Selectors (Proven from previous steps) ---
SHADOW_ROOT_HOST_ID = 'cmpwrapper'
COOKIE_ACCEPT_SELECTOR = '#cmpbntyestxt' # Selector inside the Shadow DOM
STORE_SELECT_BUTTON_SELECTOR = 'button.spar-location-selector__btn' 
SEARCH_INPUT_SELECTOR = '[data-tosca="location-search-input"]' 
FIRST_AUTOCOMPLETE_ITEM_SELECTOR = '.pac-container .pac-item:first-child'
LOCATION_SEARCH_CONTAINER = '[data-tosca="location-search-container"]' 
LOCATION_LIST_PARENT = 'div.location-overlay dialog.overlay__wrapper div.overlay__content div.overlay__content'
ALL_STORE_OPTIONS_SELECTOR = '.location-list__option' 
STORE_TITLE_RELATIVE_SELECTOR = '[data-tosca="location-overlay-option-title"]' 
STORE_BUTTON_RELATIVE_SELECTOR = 'button[data-tosca="location-overlay-option-btn"]'
# --------------------------

# --- HEADLESS CHROME OPTIONS ---
options = webdriver.ChromeOptions()
# Removed --headless=new option for debugging reliability, re-enable if desired
options.add_argument('--no-sandbox')
options.add_argument('--disable-dev-shm-usage')
options.add_argument('--window-size=1920,1080')
options.add_argument('user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36')
options.add_experimental_option("excludeSwitches", ["enable-automation"]) 
options.add_experimental_option('useAutomationExtension', False)
options.add_argument('--disable-gpu')
options.add_argument('--disable-logging')
options.add_argument('--log-level=3') 


# =================================================================================================
# LOCATION SETTING FUNCTIONS (SUCCESSFULLY TESTED)
# =================================================================================================

def click_store_select_button(driver):
    """Finds and clicks the main 'Markt wählen' button to open the location selection dialog."""
    try:
        store_button = WebDriverWait(driver, 5).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, STORE_SELECT_BUTTON_SELECTOR))
        )
        driver.execute_script("arguments[0].click();", store_button)
        return True
    except Exception:
        return False

def search_and_select_store(driver, address):
    """Executes the full search and selection flow."""
    print(f"   -> Setting location to: '{address}'...")
    
    try:
        # 1. Type the address into the search input
        search_input = WebDriverWait(driver, WAIT_TIME_SECONDS).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, SEARCH_INPUT_SELECTOR))
        )
        search_input.send_keys(address) 
        time.sleep(1.5) 

        # 2. Click the first autocomplete suggestion
        autocomplete_item = WebDriverWait(driver, 5).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, FIRST_AUTOCOMPLETE_ITEM_SELECTOR))
        )
        autocomplete_item.click()
        
        # 3. Wait for the stable element (search bar) to confirm the dialog is ready.
        WebDriverWait(driver, WAIT_TIME_SECONDS).until( 
            EC.presence_of_element_located((By.CSS_SELECTOR, LOCATION_SEARCH_CONTAINER))
        )
        time.sleep(3) # Ensure store list data loads

        # Find the Parent Container
        parent_node_element = WebDriverWait(driver, WAIT_TIME_SECONDS).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, LOCATION_LIST_PARENT))
        )
        
        # Find the first store option robustly
        store_options = parent_node_element.find_elements(By.CSS_SELECTOR, ALL_STORE_OPTIONS_SELECTOR)
        if not store_options:
            print("   -> ERROR: No store options found after search.")
            return False

        first_store_option = store_options[0]
        store_name = first_store_option.find_element(By.CSS_SELECTOR, STORE_TITLE_RELATIVE_SELECTOR).text.strip()
        
        # 4. Aggressive Click Loop
        for attempt in range(5):
            try:
                # Find the button relative to the first_store_option element
                button_to_click = first_store_option.find_element(By.CSS_SELECTOR, STORE_BUTTON_RELATIVE_SELECTOR)
                driver.execute_script("arguments[0].click();", button_to_click) 
                print(f"   -> Successfully selected store: '{store_name}'. ✅")
                return True
            except (ElementClickInterceptedException, StaleElementReferenceException):
                # Re-find elements on error
                parent_node_element = WebDriverWait(driver, 5).until(EC.presence_of_element_located((By.CSS_SELECTOR, LOCATION_LIST_PARENT)))
                store_options = parent_node_element.find_elements(By.CSS_SELECTOR, ALL_STORE_OPTIONS_SELECTOR)
                if store_options:
                    first_store_option = store_options[0]
                time.sleep(0.5)
            except Exception:
                break

        print("   -> Failed to click 'Markt wählen' after all retries. ❌")
        return False

    except TimeoutException:
        print(f"   -> Timeout during store search/selection flow. FAILED. ❌")
        return False
    except Exception as e:
        print(f"   -> Failed during store search/selection flow: {type(e).__name__}: {e}. FAILED. ❌")
        return False


# =================================================================================================
# PARSING AND SCRAPING FUNCTIONS (FROM USER'S SCRIPT)
# =================================================================================================

def get_total_pages(driver):
    """Parses the pagination text (e.g., '1 von 13') to find the total number of pages."""
    try:
        pagination_element = driver.find_element(By.CSS_SELECTOR, PAGINATION_TEXT_SELECTOR)
        text = pagination_element.text
        # Regex to find the number following 'von' (of)
        match = re.search(r'von\s+(\d+)', text)
        if match:
            return int(match.group(1))
        return 1
    except NoSuchElementException:
        return 1


def parse_product_card(card):
    """
    Extracts name, price, unit, and promotion details from a single SPAR product card.
    """
    # --- URL & NAME ---
    link_tag = card.select_one('a.product-tile__link')
    relative_url = link_tag.get('href') if link_tag and link_tag.get('href') else "N/A"
    full_url = "https://www.spar.at" + relative_url

    name1 = card.select_one('.product-tile__name1').text.strip() if card.select_one('.product-tile__name1') else ""
    name2 = card.select_one('.product-tile__name2').text.strip() if card.select_one('.product-tile__name2') else ""
    full_name = f"{name1} {name2}".strip()

    # --- UNIT/SIZE ---
    unit_tag = card.select_one('.product-tile__name3')
    unit = unit_tag.text.strip() if unit_tag else "N/A"

    # --- PRICE ---
    # Current (Sale) Price
    current_price_tag = card.select_one('.product-price__price')
    current_price = current_price_tag.text.strip().replace(',', '.').replace('€', '') if current_price_tag else "N/A"
    
    # Old (Original/Statt) Price
    old_price_tag = card.select_one('.product-price__price-old')
    old_price = old_price_tag.text.strip().replace('statt', '').replace(',', '.').replace('€', '').strip() if old_price_tag else ""
    
    # Promotion Type (Aktion!, Mengenvorteil, etc.)
    promo_tag = card.select_one('.product-price__promo-pill')
    promo_text = promo_tag.text.strip() if promo_tag else "Standard Offer Price"
    
    # Comparison Price (Per 1 kg / 1 l, etc.)
    comparison_tag = card.select_one('.product-price__comparison-price')
    comparison_price = comparison_tag.text.strip().replace('Per', '').strip() if comparison_tag else "N/A"

    return {
        "name": full_name, 
        "current_price": current_price, 
        "old_price": old_price,
        "promotion_type": promo_text,
        "unit_size": unit, 
        "comparison_price": comparison_price,
        "url": full_url
    }


def scrape_spar_offers(url, target_address):
    """
    Scrapes all promotional product data from the SPAR category page by iterating 
    through the paginated URL structure after setting a specific store location.
    """
    driver = None
    try:
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=options)
    except Exception as e:
        print(f"Error initializing WebDriver: {e}")
        return []

    print(f"Navigating to {url}...")
    driver.get(url)
    scraped_data = []

    # --- 1. HANDLE COOKIE BANNER (Using Shadow DOM logic for robustness) ---
    print("\n[Step 1] Handling cookie banner...")
    js_command_cookie = f"""
    var shadow_root_host = document.getElementById('{SHADOW_ROOT_HOST_ID}');
    if (shadow_root_host && shadow_root_host.shadowRoot) {{
        var accept_span = shadow_root_host.shadowRoot.querySelector('{COOKIE_ACCEPT_SELECTOR}');
        if (accept_span) {{
            accept_span.click();
            return true;
        }}
    }}
    return false;
    """
    try:
        WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.ID, SHADOW_ROOT_HOST_ID)))
        driver.execute_script(js_command_cookie)
        print("   -> Cookie banner successfully accepted. ✅")
        time.sleep(1) 
    except Exception:
        print("   -> No Shadow DOM cookie banner found or timed out. Continuing.")
        pass

    # --- 2. SET STORE LOCATION (Critical for localized prices) ---
    print("\n[Step 2] Setting store location...")
    if click_store_select_button(driver) and search_and_select_store(driver, target_address):
        print("   -> Store location set successfully. Reloading page to apply localization.")
        # Re-fetch the offer URL to load the page with the newly set store prices
        driver.get(url)
    else:
        print("   -> WARNING: Failed to set store location. Proceeding with default location data. ⚠️")


    # --- 3. DETERMINE TOTAL PAGES ---
    try:
        WebDriverWait(driver, WAIT_TIME_SECONDS).until(
            EC.presence_of_element_located((By.ID, PRODUCT_GRID_ID))
        )
        total_pages = get_total_pages(driver)
        print(f"\n[Step 3] Found a total of {total_pages} pages of offers to scrape.")
    except TimeoutException:
        print("\n[Step 3] Timeout waiting for product grid. Assuming 1 page.")
        total_pages = 1
    
    # --- 4. PAGE ITERATION LOOP ---
    for page_num in range(1, total_pages + 1):
        page_url = f"{BASE_URL}?inAngebot=true&page={page_num}"
        print(f"\n[Step 4] Scraping Page {page_num} of {total_pages}: {page_url}")
        
        # Navigate to the page URL (skip driver.get for the first page)
        if page_num > 1:
            driver.get(page_url)
            # Synchronize: Wait for the product grid to be present again
            WebDriverWait(driver, WAIT_TIME_SECONDS).until(
                EC.presence_of_element_located((By.ID, PRODUCT_GRID_ID))
            )
            time.sleep(1) # Small delay for content rendering
        
        # --- SCRAPE CURRENT PAGE ---
        html_content = driver.page_source
        soup = BeautifulSoup(html_content, 'html.parser')

        product_cards = soup.select(PRODUCT_CARD_SELECTOR)
        print(f"-> Found {len(product_cards)} products on this page.")

        for card in product_cards:
            try:
                product_info = parse_product_card(card)
                scraped_data.append(product_info)
            except Exception:
                continue

    # --- 5. FINAL OUTPUT ---
    final_count = len(scraped_data)
    print("\n[Step 5] Finalizing Scraping...")
    
    try:
        print(f"\nSuccessfully scraped a total of {final_count} promotional products from SPAR (Localized data).")
        
        if final_count > 0:
            print("\n--- SAMPLE SCRAPED DATA (First 5 Items) ---")
            for item in scraped_data[:5]:
                print("----------------------------------------")
                print(f"Name: {item['name']}")
                print(f"Price: €{item['current_price']} (Old: €{item['old_price'] if item['old_price'] else 'N/A'})")
                print(f"Size: {item['unit_size']} ({item['comparison_price']})")
                print(f"Promotion: {item['promotion_type']}")
                print(f"URL: {item['url']}")
            print("----------------------------------------")
            
        return scraped_data

    except Exception as e:
        print(f"\nAn error occurred during final parsing: {e}")
        return []
    finally:
        if driver:
            driver.quit()
            print("\nWebDriver closed.")

if __name__ == "__main__":
    scrape_spar_offers(URL, TARGET_ADDRESS)
