import re
import time
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
BASE_URL = "https://www.spar.at/produktwelt/lebensmittel"
# We scrape products that are 'on offer' by requesting the first page with the filter
URL = f"{BASE_URL}?inAngebot=true&page=1"
WAIT_TIME_SECONDS = 15

# --- General Selectors ---
PRODUCT_GRID_ID = "spar-plp__grid"
PRODUCT_CARD_SELECTOR = "div.spar-plp__grid-item article.product-tile"
PAGINATION_TEXT_SELECTOR = ".pagination__text"

# --- Location Setting Selectors ---
SHADOW_ROOT_HOST_ID = "cmpwrapper"
COOKIE_ACCEPT_SELECTOR = "#cmpbntyestxt"  # Selector inside the Shadow DOM
STORE_SELECT_BUTTON_SELECTOR = "button.spar-location-selector__btn"
SEARCH_INPUT_SELECTOR = '[data-tosca="location-search-input"]'

# Custom dropdown item matching SPAR's UI structure
FIRST_AUTOCOMPLETE_ITEM_SELECTOR = (
    'li.location-search__suggestion[data-tosca="location-search-suggestion"]'
)
LOCATION_SEARCH_CONTAINER = '[data-tosca="location-search-container"]'
LOCATION_LIST_PARENT = "div.location-overlay dialog.overlay__wrapper div.overlay__content div.overlay__content"
ALL_STORE_OPTIONS_SELECTOR = ".location-list__option"
OVERLAY_WRAPPER_SELECTOR = "div.location-overlay"

# Relative selectors matching SPAR's location-info schema
STORE_TITLE_RELATIVE_SELECTOR = '[data-tosca="location-info-title"]'
STORE_ADDRESS_RELATIVE_SELECTOR = '[data-tosca="location-info-address"]'
STORE_BUTTON_RELATIVE_SELECTOR = 'button[data-tosca="location-info-select-btn"]'
SELECTED_STORE_HEADER_SELECTOR = '[data-tosca="location-selector-title"]'
# --------------------------

# --- CHROME OPTIONS ---
options = webdriver.ChromeOptions()
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
# LOCATION SETTING FUNCTIONS
# =================================================================================================


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
        # 1. Type address into the search input
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


# =================================================================================================
# PARSING AND SCRAPING FUNCTIONS
# =================================================================================================


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


def parse_product_card(card):
    """Extracts name, price, unit, and promotion details from a single SPAR product card."""
    link_tag = card.select_one("a.product-tile__link")
    relative_url = (
        link_tag.get("href") if link_tag and link_tag.get("href") else "N/A"
    )
    full_url = "https://www.spar.at" + relative_url

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

    unit_tag = card.select_one(".product-tile__name3")
    unit = unit_tag.text.strip() if unit_tag else "N/A"

    current_price_tag = card.select_one(".product-price__price")
    current_price = (
        current_price_tag.text.strip().replace(",", ".").replace("€", "")
        if current_price_tag
        else "N/A"
    )

    old_price_tag = card.select_one(".product-price__price-old")
    old_price = (
        old_price_tag.text.strip()
        .replace("statt", "")
        .replace(",", ".")
        .replace("€", "")
        .strip()
        if old_price_tag
        else ""
    )

    promo_tag = card.select_one(".product-price__promo-pill")
    promo_text = promo_tag.text.strip() if promo_tag else "Standard Offer Price"

    comparison_tag = card.select_one(".product-price__comparison-price")
    comparison_price = (
        comparison_tag.text.strip().replace("Per", "").strip()
        if comparison_tag
        else "N/A"
    )

    return {
        "name": full_name,
        "current_price": current_price,
        "old_price": old_price,
        "promotion_type": promo_text,
        "unit_size": unit,
        "comparison_price": comparison_price,
        "url": full_url,
    }


def scrape_spar_offers(url, target_address):
    """Scrapes all promotional product data from the SPAR category page by iterating
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

    # --- 1. HANDLE COOKIE BANNER ---
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
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.ID, SHADOW_ROOT_HOST_ID))
        )
        driver.execute_script(js_command_cookie)
        print("   -> Cookie banner successfully accepted. ✅")
        time.sleep(1)
    except Exception:
        print("   -> No Shadow DOM cookie banner found or timed out. Continuing.")

    # --- 2. SET STORE LOCATION ---
    print("\n[Step 2] Setting store location...")
    if click_store_select_button(driver) and search_and_select_store(
        driver, target_address
    ):
        print("   -> Store location set successfully. Proceeding with scraping.")
    else:
        print(
            "   -> WARNING: Failed to set store location. Proceeding with default location data. ⚠️"
        )

    # --- 3. DETERMINE TOTAL PAGES ---
    try:
        WebDriverWait(driver, WAIT_TIME_SECONDS).until(
            EC.presence_of_element_located((By.ID, PRODUCT_GRID_ID))
        )
        total_pages = get_total_pages(driver)
        print(
            f"\n[Step 3] Found a total of {total_pages} pages of offers to scrape."
        )
    except TimeoutException:
        print("\n[Step 3] Timeout waiting for product grid. Assuming 1 page.")
        total_pages = 1

    # --- 4. PAGE ITERATION LOOP ---
    for page_num in range(1, total_pages + 1):
        page_url = f"{BASE_URL}?inAngebot=true&page={page_num}"
        print(
            f"\n[Step 4] Scraping Page {page_num} of {total_pages}: {page_url}"
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
        print(
            f"\nSuccessfully scraped a total of {final_count} promotional products from SPAR (Localized data)."
        )

        if final_count > 0:
            print("\n--- SAMPLE SCRAPED DATA (First 5 Items) ---")
            for item in scraped_data[:5]:
                print("----------------------------------------")
                print(f"Name: {item['name']}")
                print(
                    f"Price: €{item['current_price']} (Old: €{item['old_price'] if item['old_price'] else 'N/A'})"
                )
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