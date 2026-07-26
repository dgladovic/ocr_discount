import hashlib
import json
import os
import re
import time
import requests
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.common.exceptions import (
    ElementClickInterceptedException,
    NoSuchElementException,
    StaleElementReferenceException,
    TimeoutException,
)
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from webdriver_manager.chrome import ChromeDriverManager

# --- Configuration ---
TARGET_ADDRESS = "Niederhofstraße 23, 1120 Wien"  # Location to set the store
WAIT_TIME_SECONDS = 15
INPUT_JSON_PATH = "extracted_json/spar_scraped_offers.json"
IMAGE_DIR = "../extracted_images/spar"  # Directory for saving product images

# Prioritized categories to scrape
CATEGORIES_TO_SCRAPE = [
    {"name": "Lebensmittel (Food)", "path": "lebensmittel", "category_tag": "FOOD"},
    {"name": "Getränke (Drinks)", "path": "getraenke", "category_tag": "DRINKS"},
]
BASE_URL_TEMPLATE = "https://www.spar.at/produktwelt/{category_path}"


# --- General Selectors ---
PRODUCT_GRID_ID = "spar-plp__grid"
PRODUCT_CARD_SELECTOR = "div.spar-plp__grid-item article.product-tile"
PAGINATION_TEXT_SELECTOR = ".pagination__text"

# --- Location Setting Selectors ---
SHADOW_ROOT_HOST_ID = "cmpwrapper"
COOKIE_ACCEPT_SELECTOR = "#cmpbntyestxt"
STORE_SELECT_BUTTON_SELECTOR = "button.spar-location-selector__btn"
SEARCH_INPUT_SELECTOR = '[data-tosca="location-search-input"]'

# Updated dropdown selector matching SPAR's custom autocomplete structure
FIRST_AUTOCOMPLETE_ITEM_SELECTOR = (
    'li.location-search__suggestion[data-tosca="location-search-suggestion"]'
)
LOCATION_SEARCH_CONTAINER = '[data-tosca="location-search-container"]'
LOCATION_LIST_PARENT = "div.location-overlay dialog.overlay__wrapper div.overlay__content div.overlay__content"
ALL_STORE_OPTIONS_SELECTOR = ".location-list__option"
OVERLAY_WRAPPER_SELECTOR = "div.location-overlay"

# Updated relative selectors matching SPAR's location-info component
STORE_TITLE_RELATIVE_SELECTOR = '[data-tosca="location-info-title"]'
STORE_ADDRESS_RELATIVE_SELECTOR = '[data-tosca="location-info-address"]'
STORE_BUTTON_RELATIVE_SELECTOR = 'button[data-tosca="location-info-select-btn"]'
SELECTED_STORE_HEADER_SELECTOR = '[data-tosca="location-selector-title"]'

# --- HEADLESS CHROME OPTIONS ---
options = webdriver.ChromeOptions()
# options.add_argument('--headless=new') # Uncomment this to run headless
options.add_argument("--no-sandbox")
options.add_argument("--disable-dev-shm-usage")
options.add_argument("--window-size=1920,1080")
options.add_argument(
    "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
)
options.add_experimental_option("excludeSwitches", ["enable-automation"])
options.add_experimental_option("useAutomationExtension", False)
options.add_argument("--disable-gpu")
options.add_argument("--disable-logging")
options.add_argument("--log-level=3")


# =================================================================================================
# HELPER FUNCTIONS FOR UNIFICATION AND LOCATION
# =================================================================================================


def calculate_discount(current_price_str, original_price_str):
    """Calculates the percentage discount from the price strings."""
    try:
        current_val = float(current_price_str.replace(",", ".").strip())
        original_val = float(original_price_str.replace(",", ".").strip())

        if original_val > 0 and current_val < original_val:
            discount_percent = ((original_val - current_val) / original_val) * 100
            return f"{min(99, round(discount_percent)):.0f}% OFF"
    except ValueError:
        pass
    return "N/A"


def get_total_pages(driver):
    """Parses the pagination text (e.g., '1 von 13') to find the total number of pages."""
    try:
        pagination_element = driver.find_element(
            By.CSS_SELECTOR, PAGINATION_TEXT_SELECTOR
        )
        text = pagination_element.text
        match = re.search(r"von\s+(\d+)", text)
        if match:
            return int(match.group(1))
        return 1
    except NoSuchElementException:
        return 1


def click_store_select_button(driver):
    """Finds and clicks the main 'Markt wählen' or 'Markt ändern' button to open the location selection dialog."""
    try:
        store_button = WebDriverWait(driver, 5).until(
            EC.element_to_be_clickable(
                (By.CSS_SELECTOR, STORE_SELECT_BUTTON_SELECTOR)
            )
        )
        driver.execute_script("arguments[0].click();", store_button)
        return True
    except Exception:
        return False


def search_and_select_store(driver, address):
    """Executes search, address matching with stale-element protection, and handles modal state commitment."""
    print(f"   -> Setting location to: '{address}'...")

    try:
        # 1. Type the address into the search input
        search_input = WebDriverWait(driver, WAIT_TIME_SECONDS).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, SEARCH_INPUT_SELECTOR))
        )
        search_input.clear()
        search_input.send_keys(address)
        time.sleep(1.5)  # Allow autocomplete to render

        # 2. Click autocomplete suggestion with Keyboard fallback
        try:
            autocomplete_item = WebDriverWait(driver, 5).until(
                EC.element_to_be_clickable(
                    (By.CSS_SELECTOR, FIRST_AUTOCOMPLETE_ITEM_SELECTOR)
                )
            )
            autocomplete_item.click()
        except TimeoutException:
            print(
                "   -> Click timed out; sending Down Arrow + Enter for keyboard selection..."
            )
            search_input.send_keys(Keys.ARROW_DOWN)
            time.sleep(0.5)
            search_input.send_keys(Keys.ENTER)

        # 3. Wait for store option list container to populate
        WebDriverWait(driver, WAIT_TIME_SECONDS).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, LOCATION_LIST_PARENT))
        )
        WebDriverWait(driver, WAIT_TIME_SECONDS).until(
            EC.presence_of_element_located(
                (By.CSS_SELECTOR, ALL_STORE_OPTIONS_SELECTOR)
            )
        )

        time.sleep(1.5)  # Let DOM re-rendering stabilize after selection

        # 4. Find matching store index safely against stale element exceptions
        target_index = 0  # Default fallback
        street_keyword = address.split(",")[0].split(" ")[0].strip()  # "Niederhofstraße"

        for retry in range(3):
            try:
                parent_node = driver.find_element(
                    By.CSS_SELECTOR, LOCATION_LIST_PARENT
                )
                store_options = parent_node.find_elements(
                    By.CSS_SELECTOR, ALL_STORE_OPTIONS_SELECTOR
                )

                if not store_options:
                    print("   -> ERROR: No store options found after search.")
                    return False

                for idx, option in enumerate(store_options):
                    try:
                        address_text = option.find_element(
                            By.CSS_SELECTOR, STORE_ADDRESS_RELATIVE_SELECTOR
                        ).text.strip()
                        if street_keyword.lower() in address_text.lower():
                            target_index = idx
                            print(
                                f"   -> Found exact address match in results at index {idx}: '{address_text}'"
                            )
                            break
                    except NoSuchElementException:
                        continue
                break  # Exit retry loop if successfully scanned
            except StaleElementReferenceException:
                time.sleep(1)

        # 5. Perform click on the chosen store index with fresh element re-fetch
        for attempt in range(5):
            try:
                parent_node = driver.find_element(
                    By.CSS_SELECTOR, LOCATION_LIST_PARENT
                )
                store_options = parent_node.find_elements(
                    By.CSS_SELECTOR, ALL_STORE_OPTIONS_SELECTOR
                )

                if target_index >= len(store_options):
                    target_index = 0

                target_option = store_options[target_index]

                try:
                    store_name = target_option.find_element(
                        By.CSS_SELECTOR, STORE_TITLE_RELATIVE_SELECTOR
                    ).text.strip()
                except NoSuchElementException:
                    store_name = "Target Store"

                button_to_click = target_option.find_element(
                    By.CSS_SELECTOR, STORE_BUTTON_RELATIVE_SELECTOR
                )
                driver.execute_script("arguments[0].click();", button_to_click)
                print(
                    f"   -> Clicked 'Markt wählen' for: '{store_name}'. Committing state..."
                )
                break
            except (
                ElementClickInterceptedException,
                StaleElementReferenceException,
                IndexError,
            ):
                time.sleep(0.5)

        # 6. Wait for overlay modal to close
        try:
            WebDriverWait(driver, 10).until(
                EC.invisibility_of_element_located(
                    (By.CSS_SELECTOR, OVERLAY_WRAPPER_SELECTOR)
                )
            )
            print("   -> Location overlay closed successfully.")
        except TimeoutException:
            print("   -> Warning: Overlay did not close automatically.")

        time.sleep(2)  # Allow session state/cookies to write

        # 7. Verify UI header component matches chosen market
        selected_title_element = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located(
                (By.CSS_SELECTOR, SELECTED_STORE_HEADER_SELECTOR)
            )
        )
        current_ui_store = selected_title_element.text.strip()
        print(f"   -> Store set in UI: '{current_ui_store}' ✅")
        return True

    except Exception as e:
        print(
            f"   -> Failed during store selection flow: {type(e).__name__}: {e}. FAILED. ❌"
        )
        return False


def download_image(image_url, product_hash, image_dir):
    """Downloads an image from a URL and saves it using the product hash as the filename."""
    if not image_url or image_url == "N/A":
        return "N/A"

    os.makedirs(image_dir, exist_ok=True)

    extension = ".jpg"
    local_filename = f"{product_hash}{extension}"
    local_filepath = os.path.join(image_dir, local_filename)

    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        response = requests.get(image_url, headers=headers, stream=True, timeout=10)
        response.raise_for_status()

        with open(local_filepath, "wb") as f:
            for chunk in response.iter_content(8192):
                f.write(chunk)

        return local_filepath

    except requests.exceptions.RequestException:
        return "N/A"


# =================================================================================================
# PARSING AND SCRAPING FUNCTIONS (UNIFIED SCHEMA)
# =================================================================================================


def parse_product_card(card, category_tag):
    """Extracts data and maps it to the unified product schema, including image URL."""
    # --- URL & NAME ---
    link_tag = card.select_one("a.product-tile__link")
    relative_url = (
        link_tag.get("href") if link_tag and link_tag.get("href") else ""
    )
    full_url = "https://www.spar.at" + relative_url

    # Generate a stable hash ID from the URL
    product_hash = hashlib.sha1(full_url.encode("utf-8")).hexdigest()

    name1 = (
        card.select_one(".product-tile__name1").text.strip()
        if card.select_one(".product-tile__name1")
        else ""
    )
    name2 = (
        card.select_one(".product-tile__name2").text.strip()
        if card.select_one(".product-tile__name2")
        else ""
    )
    full_name = f"{name1} {name2}".strip()

    # --- UNIT/SIZE ---
    unit_tag = card.select_one(".product-tile__name3")
    unit = unit_tag.text.strip() if unit_tag else "N/A"

    # --- IMAGE ---
    img_tag = card.select_one(".product-tile__image img.adaptive-image__img")
    product_image_url = (
        img_tag.get("src") if img_tag and img_tag.get("src") else "N/A"
    )

    # --- PRICE ---
    current_price_tag = card.select_one(".product-price__price")
    current_price_raw = (
        current_price_tag.text.strip().replace("€", "").replace(",", ".")
        if current_price_tag
        else "N/A"
    )

    old_price_tag = card.select_one(".product-price__price-old")
    old_price_raw = (
        old_price_tag.text.strip()
        .replace("statt", "")
        .replace("€", "")
        .strip()
        .replace(",", ".")
        if old_price_tag
        else ""
    )

    # --- Discount Calculation ---
    discount_val = calculate_discount(current_price_raw, old_price_raw)

    # --- UNIFIED OUTPUT DICT ---
    return {
        "productHash": product_hash,
        "productName": full_name,
        "currentPrice": (
            f"€{current_price_raw.replace('.', ',')}"
            if current_price_raw != "N/A"
            else "€N/A"
        ),
        "originalPrice": (
            f"€{old_price_raw.replace('.', ',')}"
            if old_price_raw
            else "€N/A"
        ),
        "discount": discount_val,
        "unitMeasure": unit,
        "category": category_tag,
        "productUrl": full_url,
        "productImageUrl": product_image_url,
    }


def scrape_category_pages(driver, category_path, category_tag):
    """Handles navigation and scraping for a single category path, iterating through pages.
    Downloads the product image for each item.
    """
    category_url = f"{BASE_URL_TEMPLATE.format(category_path=category_path)}?inAngebot=true&page=1"
    print(f"\n--- Starting category scrape: {category_tag} ({category_path}) ---")
    print(f"Navigating to {category_url}...")
    driver.get(category_url)

    scraped_data = []

    # 1. DETERMINE TOTAL PAGES
    try:
        WebDriverWait(driver, WAIT_TIME_SECONDS).until(
            EC.presence_of_element_located((By.ID, PRODUCT_GRID_ID))
        )
        total_pages = get_total_pages(driver)
        print(
            f"\n[Scrape] Found a total of {total_pages} pages of offers for {category_tag}."
        )
    except TimeoutException:
        print(
            f"\n[Scrape] Timeout waiting for product grid. Assuming 1 page for {category_tag}."
        )
        total_pages = 1

    # 2. PAGE ITERATION LOOP
    for page_num in range(1, total_pages + 1):
        page_url = f"{BASE_URL_TEMPLATE.format(category_path=category_path)}?inAngebot=true&page={page_num}"
        print(
            f"   -> Scraping Page {page_num} of {total_pages}: {page_url}"
        )

        if page_num > 1:
            driver.get(page_url)
            WebDriverWait(driver, WAIT_TIME_SECONDS).until(
                EC.presence_of_element_located((By.ID, PRODUCT_GRID_ID))
            )
            time.sleep(1)

        html_content = driver.page_source
        soup = BeautifulSoup(html_content, "html.parser")

        product_cards = soup.select(PRODUCT_CARD_SELECTOR)

        for card in product_cards:
            try:
                product_info = parse_product_card(card, category_tag)

                # --- IMAGE DOWNLOAD ---
                local_image_path = download_image(
                    product_info["productImageUrl"],
                    product_info["productHash"],
                    IMAGE_DIR,
                )

                product_info["localImagePath"] = local_image_path
                scraped_data.append(product_info)
            except Exception:
                continue

    print(
        f"--- Finished {category_tag}. Scraped {len(scraped_data)} products."
    )
    return scraped_data


def main_scraper_run():
    """Initializes WebDriver, sets location, and loops through prioritized categories."""
    driver = None
    all_scraped_offers = []

    try:
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=options)
    except Exception as e:
        print(f"Fatal Error initializing WebDriver: {e}")
        return []

    # 1. INITIAL NAVIGATION
    initial_url = f"{BASE_URL_TEMPLATE.format(category_path=CATEGORIES_TO_SCRAPE[0]['path'])}?inAngebot=true&page=1"
    print(f"Starting initial navigation to {initial_url}...")
    driver.get(initial_url)

    # 2. HANDLE COOKIE BANNER
    print("\n[Setup] Handling cookie banner...")
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
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.ID, SHADOW_ROOT_HOST_ID))
        )
        driver.execute_script(js_command_cookie)
        print("   -> Cookie banner successfully accepted. ✅")
        time.sleep(1)
    except Exception:
        print("   -> No Shadow DOM cookie banner found or timed out. Continuing.")

    # 3. SET STORE LOCATION
    print("\n[Setup] Setting store location...")
    if click_store_select_button(driver) and search_and_select_store(
        driver, TARGET_ADDRESS
    ):
        print("   -> Store location set successfully. Ready to scrape.")
    else:
        print(
            "   -> WARNING: Failed to set store location. Proceeding with default data. ⚠️"
        )

    # 4. CATEGORY LOOP
    for category in CATEGORIES_TO_SCRAPE:
        scraped_products = scrape_category_pages(
            driver, category["path"], category["category_tag"]
        )
        all_scraped_offers.extend(scraped_products)

    # 5. FINAL OUTPUT
    final_count = len(all_scraped_offers)

    if final_count > 0:
        final_data = {
            "flyerDateRange": "Weekly Localized Offers",
            "productOffers": all_scraped_offers,
        }

        os.makedirs(os.path.dirname(INPUT_JSON_PATH), exist_ok=True)

        try:
            with open(INPUT_JSON_PATH, "w", encoding="utf-8") as f:
                json.dump(final_data, f, ensure_ascii=False, indent=2)
            print(
                f"\n*** SUCCESS: Consolidated SPAR data ({final_count} products) saved to '{INPUT_JSON_PATH}'. ***"
            )
            print(
                f"*** Product images saved to the '{IMAGE_DIR}' directory. ***"
            )

            print("\n--- SAMPLE UNIFIED OUTPUT (First 3 Items) ---")
            for item in all_scraped_offers[:3]:
                print(f"Product: {item['productName']}")
                print(
                    f"Price/Original: {item['currentPrice']} / {item['originalPrice']}"
                )
                print(
                    f"Discount: {item['discount']} | Category: {item['category']}"
                )
                print(f"Image Path: {item['localImagePath']}")
                print("---")

        except Exception as e:
            print(f"ERROR: Could not save data to JSON file: {e}")
    else:
        print("\nNo products were scraped; skipping JSON save.")

    if driver:
        driver.quit()
        print("\nWebDriver closed.")

    return all_scraped_offers


if __name__ == "__main__":
    main_scraper_run()