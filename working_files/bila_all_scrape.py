"""
Standalone Billa Web Catalog Scraper (Test Run).
Scrapes product metadata and downloads studio images to local disk.
No database or ingestion pipeline dependencies.
"""

import os
import re
import json
import time
import requests
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.common.exceptions import (
    TimeoutException,
    NoSuchElementException,
)
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from webdriver_manager.chrome import ChromeDriverManager

# --- CONFIGURATION ---
# Note: Base URL now explicitly includes /kategorie
BASE_CATEGORY_URL = "https://shop.billa.at/kategorie"
WAIT_TIME_SECONDS = 15

# Set how many pages to scrape per category (start with 1-2 for testing; increase for full catalog)
MAX_PAGES_PER_CATEGORY = 2

# Local storage paths in current directory
OUTPUT_DIR = "billa_scraped_data"
IMAGE_DIR = os.path.join(OUTPUT_DIR, "images")
OUTPUT_JSON_PATH = os.path.join(OUTPUT_DIR, "billa_catalog.json")

os.makedirs(IMAGE_DIR, exist_ok=True)

# Selectors
PRODUCT_GRID_SELECTOR = ".ws-product-grid"
PRODUCT_CARD_SELECTOR = "li[data-test='product-tile']"

# =========================================================================
# BILLA CATEGORY MAPPING (Food & Drinks)
# =========================================================================
BILLA_CATEGORIES = [
    {"slug": "obst-und-gemuese-13751", "category": "Fresh Produce", "default_type": "produce_vegetable"},
    {"slug": "brot-und-gebaeck-15520", "category": "Bread & Bakery", "default_type": "bakery_bread"},
    {"slug": "fleisch-wurst-und-fisch-15388", "category": "Meat & Poultry", "default_type": "meat_sausage"},
    {"slug": "kuehlwaren-15416", "category": "Dairy & Eggs", "default_type": "dairy_milk"},
    {"slug": "getraenke-13784", "category": "Drinks & Beverages", "default_type": "drinks_soda"},
    {"slug": "vorratsschrank-15012", "category": "Pantry & Baking", "default_type": "pantry_pasta"},
    {"slug": "tiefkuehl-15415", "category": "Frozen Foods", "default_type": "frozen_meal"},
    {"slug": "schnelle-kueche-15389", "category": "Miscellaneous", "default_type": "misc_other"},
    {"slug": "platten-broetchen-und-co-15409", "category": "Bread & Bakery", "default_type": "bakery_rolls"},
    {"slug": "rein-pflanzlich-15207", "category": "Dairy & Eggs", "default_type": "dairy_plant_milk"},
    {"slug": "kueche-haushalt-und-garten-15320", "category": "Household & Cleaning", "default_type": "household_cleaner"},
    {"slug": "drogerie-und-kosmetik-15274", "category": "Health & Beauty", "default_type": "beauty_skincare"},
    {"slug": "haustier-15672", "category": "Pet Supplies", "default_type": "pet_dogfood"},
    {"slug": "baby-und-kleinkind-15671", "category": "Miscellaneous", "default_type": "misc_other"},
]

# Headless Chrome Options
options = webdriver.ChromeOptions()
# options.add_argument("--headless=new")
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


def slugify(text: str) -> str:
    text = str(text).lower().strip()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[-\s]+", "_", text)
    return text[:45].strip("_")


def download_image_locally(image_url: str, product_name: str) -> str | None:
    """Downloads Billa Commercetools studio photo to billa_scraped_data/images/."""
    if not image_url or not image_url.startswith("http"):
        return None

    filename = f"billa_web_{slugify(product_name)}.jpg"
    local_path = os.path.join(IMAGE_DIR, filename)

    if os.path.exists(local_path):
        return local_path

    try:
        res = requests.get(image_url, timeout=10, headers={"User-Agent": "Mozilla/5.0"})
        if res.status_code == 200:
            with open(local_path, "wb") as f:
                f.write(res.content)
            return local_path
    except Exception as e:
        print(f"      [!] Failed to download image for '{product_name}': {e}")
    return None


def resolve_product_type_and_category(full_name: str, cat_cfg: dict) -> tuple[str, str]:
    """Assigns strict schema category and category-prefixed product_type."""
    n = full_name.lower()
    cat = cat_cfg["category"]

    if cat == "Drinks & Beverages":
        if any(w in n for w in ["bier", "märzen", "radler", "pils", "stiegl", "gösser", "ottakringer", "wieselburger"]):
            return cat, "drinks_beer"
        if any(w in n for w in ["wein", "spritzer", "zweigelt", "rotwein", "weißwein", "sekt", "prosecco"]):
            return cat, "drinks_wine"
        if any(w in n for w in ["wasser", "mineral", "römerquelle", "waldquelle", "gasteiner"]):
            return cat, "drinks_water"
        if any(w in n for w in ["saft", "orange", "apfel", "multivitamin", "happy day", "sirup"]):
            return cat, "drinks_juice"
        if any(w in n for w in ["kaffee", "bohnen", "espresso", "barista"]):
            return cat, "drinks_coffee"
        if any(w in n for w in ["tee", "kamille", "kräuter", "früchte"]):
            return cat, "drinks_tea"
        if any(w in n for w in ["vodka", "gin", "rum", "whisky", "likör", "schnaps"]):
            return cat, "drinks_spirits"
        return cat, "drinks_soda"

    if cat == "Dairy & Eggs":
        if any(w in n for w in ["käse", "gouda", "mozzarella", "parmesan", "ricotta", "camembert", "emmentaler"]):
            return cat, "dairy_cheese"
        if any(w in n for w in ["joghurt", "yogurt"]):
            return cat, "dairy_yogurt"
        if any(w in n for w in ["butter", "margarine"]):
            return cat, "dairy_butter"
        if any(w in n for w in ["eier", "hühnereier", "bodenhaltung", "freiland"]):
            return cat, "dairy_eggs"
        if any(w in n for w in ["topfen", "quark"]):
            return cat, "dairy_quark"
        if any(w in n for w in ["hafer", "mandel", "soja", "pflanzendrink"]):
            return cat, "dairy_plant_milk"
        if any(w in n for w in ["obers", "sahne", "schlagobers", "creme"]):
            return cat, "dairy_cream"
        return cat, "dairy_milk"

    if cat == "Fresh Produce":
        if any(w in n for w in ["apfel", "banane", "beere", "traube", "zitrone", "orange", "birne", "mango"]):
            return cat, "produce_fruit"
        if any(w in n for w in ["salat", "eisberg", "rucola", "spinat"]):
            return cat, "produce_salad"
        if any(w in n for w in ["petersilie", "basilikum", "schnittlauch", "kräuter"]):
            return cat, "produce_herbs"
        return cat, "produce_vegetable"

    if cat == "Meat & Poultry":
        if any(w in n for w in ["fisch", "lachs", "thunfisch", "forelle", "garnele"]):
            return "Fish & Seafood", "fish_fresh"
        if any(w in n for w in ["huhn", "hähnchen", "pute", "geflügel"]):
            return cat, "meat_chicken"
        if any(w in n for w in ["rind", "faschiertes", "steak", "beiried"]):
            return cat, "meat_beef"
        if any(w in n for w in ["wurst", "schinken", "salami", "speck", "wiener"]):
            return cat, "meat_sausage"
        return cat, "meat_pork"

    if cat == "Bread & Bakery":
        if any(w in n for w in ["semmel", "weckerl", "brötchen", "kornspitz"]):
            return cat, "bakery_rolls"
        if any(w in n for w in ["torte", "kuchen", "muffin"]):
            return cat, "bakery_cake"
        if any(w in n for w in ["croissant", "plunder", "krapfen"]):
            return cat, "bakery_pastry"
        return cat, "bakery_bread"

    if cat == "Frozen Foods":
        if any(w in n for w in ["eis", "ice cream", "gelato"]):
            return cat, "frozen_icecream"
        if any(w in n for w in ["pizza"]):
            return cat, "frozen_pizza"
        if any(w in n for w in ["fisch", "garnelen"]):
            return cat, "frozen_fish"
        if any(w in n for w in ["gemüse", "erbsen", "spinat"]):
            return cat, "frozen_vegetable"
        return cat, "frozen_meal"

    if cat == "Snacks & Confectionery":
        if any(w in n for w in ["schokolade", "praline", "riegel"]):
            return cat, "snacks_chocolate"
        if any(w in n for w in ["chips", "popcorn", "nachos", "tortilla"]):
            return cat, "snacks_chips"
        if any(w in n for w in ["keks", "waffel", "cookies", "biskuit"]):
            return cat, "snacks_cookies"
        if any(w in n for w in ["nüsse", "mandeln", "erdnüsse", "cashew"]):
            return cat, "snacks_nuts"
        return cat, "snacks_candy"

    if cat == "Pantry & Baking":
        if any(w in n for w in ["nudeln", "pasta", "spaghetti", "penne"]):
            return cat, "pantry_pasta"
        if any(w in n for w in ["reis"]):
            return cat, "pantry_rice"
        if any(w in n for w in ["öl", "essig", "olivenöl"]):
            return cat, "pantry_oil"
        if any(w in n for w in ["salz", "pfeffer", "gewürz", "oregano"]):
            return cat, "pantry_spice"
        if any(w in n for w in ["mehl"]):
            return cat, "pantry_flour"
        if any(w in n for w in ["sauce", "pesto", "ketchup", "senf"]):
            return cat, "pantry_sauce"
        if any(w in n for w in ["dose", "bohnen", "mais"]):
            return cat, "pantry_canned"
        return cat, "pantry_baking"

    return cat, cat_cfg["default_type"]


def parse_billa_product_card(card, cat_cfg: dict) -> dict:
    title_el = card.select_one('[data-test="product-title"]') or card.select_one('.ws-product-title')
    full_name = title_el.text.strip() if title_el else "Unknown Product"

    desc_el = card.select_one('[data-test="product-information-piece-description"] li')
    package_size = desc_el.text.strip() if desc_el else ""

    current_price = None
    sr_price = card.select_one('.ws-product-price-value .d-sr-only')
    if sr_price:
        current_price = sr_price.text.replace("€", "").replace("\xa0", "").replace(",", ".").strip()
    else:
        main_val = card.select_one('.ws-product-price-value__main')
        super_val = card.select_one('[data-test="product-price-superscript"]')
        if main_val and super_val:
            cents = re.sub(r'\D', '', super_val.text)
            current_price = f"{main_val.text.strip()}.{cents}"

    img_tag = card.select_one('[data-test="product-tile-image"] img') or card.select_one('img.ws-product-image')
    image_url = None
    if img_tag:
        image_url = img_tag.get('src') or img_tag.get('data-src')

    local_image_path = download_image_locally(image_url, full_name)
    category, product_type = resolve_product_type_and_category(full_name, cat_cfg)

    return {
        "productName": full_name,
        "category": category,
        "productType": product_type,
        "brand": None,
        "packageSize": package_size,
        "currentPrice": current_price,
        "originalPrice": None,
        "remoteImageUrl": image_url,
        "localImagePath": local_image_path,
    }


def handle_billa_cookie_banner(driver):
    """
    Penetrates the Usercentrics Shadow Root to click 'Ablehnen' (Deny).
    """
    print("   -> Checking for Billa cookie banner (Usercentrics Shadow DOM)...")
    
    # Wait for the shadow root host element to mount into the DOM
    time.sleep(2)

    # 1. Native Selenium 4 Shadow Root access
    for host_selector in ["#usercentrics-root", "div#usercentrics-root", "#usercentrics-cmp-ui", "aside#usercentrics-cmp-ui"]:
        try:
            shadow_host = driver.find_element(By.CSS_SELECTOR, host_selector)
            if shadow_host:
                shadow_root = shadow_host.shadow_root
                deny_btn = shadow_root.find_element(By.CSS_SELECTOR, "button#deny, button[data-action-type='deny'], button.uc-deny-button, button#accept")
                deny_btn.click()
                print("   -> Clicked cookie banner button via Selenium 4 ShadowRoot! ✅")
                time.sleep(1.5)
                return
        except Exception:
            continue

    # 2. JavaScript Shadow Root traversal fallback
    js_shadow_click = """
    var hosts = ['#usercentrics-root', '#usercentrics-cmp-ui', 'aside#usercentrics-cmp-ui', 'div.cmp-wrapper'];
    for (var i = 0; i < hosts.length; i++) {
        var host = document.querySelector(hosts[i]);
        if (host && host.shadowRoot) {
            var btn = host.shadowRoot.querySelector('button#deny') || 
                      host.shadowRoot.querySelector('button[data-action-type="deny"]') || 
                      host.shadowRoot.querySelector('button#accept');
            if (btn) {
                btn.click();
                return true;
            }
        }
    }
    // Check if directly in Light DOM
    var lightBtn = document.querySelector('button#deny') || document.querySelector('button#accept');
    if (lightBtn) {
        lightBtn.click();
        return true;
    }
    return false;
    """
    try:
        clicked = driver.execute_script(js_shadow_click)
        if clicked:
            print("   -> Clicked cookie banner button via JavaScript ShadowRoot! ✅")
            time.sleep(1.5)
        else:
            print("   -> No active Usercentrics banner detected. Proceeding.")
    except Exception as e:
        print(f"   -> Note on cookie check: {e}")


def get_billa_total_pages(soup) -> int:
    page_links = soup.select('[data-test="pagination-item"] a')
    page_numbers = []
    for link in page_links:
        txt = link.text.strip()
        if txt.isdigit():
            page_numbers.append(int(txt))
    return max(page_numbers) if page_numbers else 1


def main():
    driver = None
    all_scraped_products = []

    try:
        print("[1/3] Launching headless browser...")
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=options)

        # 1. Open first category to dismiss cookie banner
        first_cat_url = f"{BASE_CATEGORY_URL}/{BILLA_CATEGORIES[0]['slug']}"
        print(f"[2/3] Loading initial category to clear cookies: {first_cat_url}...")
        driver.get(first_cat_url)
        handle_billa_cookie_banner(driver)

        print(f"\n[3/3] Crawling {len(BILLA_CATEGORIES)} Billa Categories (max {MAX_PAGES_PER_CATEGORY} pages each)...")

        # --- OUTER LOOP: CATEGORIES ---
        for cat_idx, cat_cfg in enumerate(BILLA_CATEGORIES, start=1):
            # FIXED URL: includes /kategorie/
            base_cat_url = f"{BASE_CATEGORY_URL}/{cat_cfg['slug']}"
            print(f"\n" + "=" * 60)
            print(f"[{cat_idx}/{len(BILLA_CATEGORIES)}] Scraping: {cat_cfg['category']} › {cat_cfg['slug']}")
            print(f"URL: {base_cat_url}")
            print("=" * 60)

            driver.get(base_cat_url)

            try:
                WebDriverWait(driver, WAIT_TIME_SECONDS).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, PRODUCT_GRID_SELECTOR))
                )
                time.sleep(1.5)
            except TimeoutException:
                print(f"     [!] Timeout loading category grid: {base_cat_url}")
                continue

            soup = BeautifulSoup(driver.page_source, "html.parser")
            total_cat_pages = get_billa_total_pages(soup)
            pages_to_crawl = min(total_cat_pages, MAX_PAGES_PER_CATEGORY)

            # --- INNER LOOP: PAGES ---
            for page in range(1, pages_to_crawl + 1):
                # FIXED URL: includes /kategorie/ and ?page=
                page_url = f"{base_cat_url}?page={page}"
                print(f"  -> Page {page}/{pages_to_crawl} ({page_url})")

                if page > 1:
                    driver.get(page_url)
                    try:
                        WebDriverWait(driver, WAIT_TIME_SECONDS).until(
                            EC.presence_of_element_located((By.CSS_SELECTOR, PRODUCT_GRID_SELECTOR))
                        )
                        time.sleep(1.5)
                    except TimeoutException:
                        break

                page_soup = BeautifulSoup(driver.page_source, "html.parser")
                cards = page_soup.select(PRODUCT_CARD_SELECTOR)
                print(f"     Found {len(cards)} products.")

                for card in cards:
                    try:
                        product = parse_billa_product_card(card, cat_cfg)
                        all_scraped_products.append(product)
                    except Exception as card_err:
                        print(f"     [!] Error parsing card: {card_err}")
                        continue

    finally:
        if driver:
            driver.quit()
            print("\n[!] Browser closed.")

    # Save output to local JSON
    print(f"\nSaving results locally to '{OUTPUT_JSON_PATH}'...")
    with open(OUTPUT_JSON_PATH, "w", encoding="utf-8") as f:
        json.dump(all_scraped_products, f, ensure_ascii=False, indent=2)

    image_count = sum(1 for p in all_scraped_products if p.get("localImagePath"))
    print("\n" + "=" * 60)
    print("BILLA SCRAPE COMPLETE SUMMARY:")
    print(f" • Total Products Scraped  : {len(all_scraped_products)}")
    print(f" • Studio Photos Downloaded : {image_count}")
    print(f" • JSON Output Saved to     : {OUTPUT_JSON_PATH}")
    print(f" • Images Directory         : {IMAGE_DIR}/")
    print("=" * 60)


if __name__ == "__main__":
    main()