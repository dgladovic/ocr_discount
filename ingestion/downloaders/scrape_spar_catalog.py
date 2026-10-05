"""
Standalone Spar Web Catalog Scraper.
Covers all Food and Drink subcategories, extracts metadata,
detects organic/Bio status from DOM badges, and downloads studio product images to local disk.
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
    NoSuchElementException,
    TimeoutException,
)
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from webdriver_manager.chrome import ChromeDriverManager

# --- CONFIGURATION ---
TARGET_ADDRESS = "Niederhofstraße 23, 1120 Wien"
WAIT_TIME_SECONDS = 15

# Set how many pages to scrape per category (start with 1-2 for testing; increase for full catalog)
MAX_PAGES_PER_CATEGORY = 100

# Local storage paths in current directory
OUTPUT_DIR = "spar_scraped_data"
IMAGE_DIR = os.path.join(OUTPUT_DIR, "images")
OUTPUT_JSON_PATH = os.path.join(OUTPUT_DIR, "spar_catalog.json")

os.makedirs(IMAGE_DIR, exist_ok=True)

# Selectors
PRODUCT_GRID_ID = "spar-plp__grid"
PRODUCT_CARD_SELECTOR = "div.spar-plp__grid-item article.product-tile"
PAGINATION_TEXT_SELECTOR = ".pagination__text"

SHADOW_ROOT_HOST_ID = "cmpwrapper"
COOKIE_ACCEPT_SELECTOR = "#cmpbntyestxt"
STORE_SELECT_BUTTON_SELECTOR = "button.spar-location-selector__btn"
SEARCH_INPUT_SELECTOR = '[data-tosca="location-search-input"]'
FIRST_AUTOCOMPLETE_ITEM_SELECTOR = 'li.location-search__suggestion[data-tosca="location-search-suggestion"]'
LOCATION_LIST_PARENT = "div.location-overlay dialog.overlay__wrapper div.overlay__content div.overlay__content"
ALL_STORE_OPTIONS_SELECTOR = ".location-list__option"
OVERLAY_WRAPPER_SELECTOR = "div.location-overlay"
STORE_BUTTON_RELATIVE_SELECTOR = 'button[data-tosca="location-info-select-btn"]'

# =========================================================================
# COMPLETE CATEGORY MAP: FOOD & DRINKS
# =========================================================================
SPAR_CATEGORIES = [
    # --- FOOD CATEGORIES ---
    {"slug": "obst-gemuese", "category": "Fresh Produce", "default_type": "produce_vegetable"},
    {"slug": "brot-gebaeck", "category": "Bread & Bakery", "default_type": "bakery_bread"},
    {"slug": "milchprodukte-alternativen", "category": "Dairy & Eggs", "default_type": "dairy_milk"},
    {"slug": "tiefkuehlprodukte", "category": "Frozen Foods", "default_type": "frozen_meal"},
    {"slug": "wurst-fleisch-eier-fisch", "category": "Meat & Poultry", "default_type": "meat_sausage"},
    {"slug": "beilagen-essig-oel-gewuerze", "category": "Pantry & Baking", "default_type": "pantry_pasta"},
    {"slug": "backen-fruehstueck", "category": "Pantry & Baking", "default_type": "pantry_baking"},
    {"slug": "suesses-salziges", "category": "Snacks & Confectionery", "default_type": "snacks_chocolate"},
    {"slug": "schnelle-kueche-to-go", "category": "Miscellaneous", "default_type": "misc_other"},
    {"slug": "babynahrung", "category": "Miscellaneous", "default_type": "misc_other"},

    # --- DRINK CATEGORIES: ALCOHOLIC & SPECIALTY ---
    {"slug": "bier", "category": "Drinks & Beverages", "default_type": "drinks_beer"},
    {"slug": "weine", "category": "Drinks & Beverages", "default_type": "drinks_wine"},
    {"slug": "schaumwein", "category": "Drinks & Beverages", "default_type": "drinks_wine"},
    {"slug": "spirituosen", "category": "Drinks & Beverages", "default_type": "drinks_spirits"},
    {"slug": "premixes", "category": "Drinks & Beverages", "default_type": "drinks_spirits"},
    {"slug": "alkoholische-heissgetraenke", "category": "Drinks & Beverages", "default_type": "drinks_wine"},
    {"slug": "alkohlfreie-weine-schaumweine", "category": "Drinks & Beverages", "default_type": "drinks_wine"},

    # --- DRINK CATEGORIES: HOT BEVERAGES ---
    {"slug": "kaffee", "category": "Drinks & Beverages", "default_type": "drinks_coffee"},
    {"slug": "tee", "category": "Drinks & Beverages", "default_type": "drinks_tea"},
    {"slug": "kakao", "category": "Drinks & Beverages", "default_type": "drinks_coffee"},

    # --- DRINK CATEGORIES: REFRESHMENTS & WATER ---
    {"slug": "mineralwasser-soda", "category": "Drinks & Beverages", "default_type": "drinks_water"},
    {"slug": "softdrinks-saefte", "category": "Drinks & Beverages", "default_type": "drinks_soda"},
    {"slug": "energy-drinks-eiskaffee", "category": "Drinks & Beverages", "default_type": "drinks_soda"},
    {"slug": "isotonische-getraenke-proteinpulver", "category": "Drinks & Beverages", "default_type": "drinks_soda"},
]

# Headless Chrome Options
options = webdriver.ChromeOptions()
options.add_argument("--headless=new")
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
    """Downloads high-res studio image to spar_scraped_data/images/."""
    if not image_url or not image_url.startswith("http"):
        return None

    filename = f"spar_web_{slugify(product_name)}.jpg"
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


def detect_spar_organic(card, full_name: str, brand: str | None) -> str:
    """
    Detects if a Spar product is organic ('yes' vs 'no').
    Inspects Spar's DOM badges (.product-tile__badges), image alt/src,
    and brand/title keywords (e.g. SPAR Natur*pur, Bio).
    """
    text_to_check = f"{full_name} {brand or ''}".lower()

    # 1. Check Spar's organic trademark brands & title keywords
    if any(b in text_to_check for b in ["natur*pur", "natur pur", "demeter", "bioland", "ja! natürlich"]):
        return "yes"
    if re.search(r"\bbio\b", text_to_check) or "biologisch" in text_to_check:
        return "yes"

    # 2. Check Spar's on-card badge icons (.product-tile__badges)
    badges = card.select(".product-tile__badges span, .product-tile__badges img, [data-tosca*='product-tile-badge']")
    for badge in badges:
        title = (badge.get("title") or "").strip().lower()
        alt = (badge.get("alt") or "").strip().lower()
        src = (badge.get("src") or "").strip().lower()

        # Matches span title="Bio", img alt="Bio", or img src containing "produktweltBIO"
        if "bio" in title or "bio" in alt or "produktweltbio" in src or "biologisch" in title:
            return "yes"

    return "no"


def resolve_product_type_and_category(full_name: str, cat_cfg: dict) -> tuple[str, str]:
    """
    Assigns strict schema category and category-prefixed product_type.
    """
    n = full_name.lower()
    cat = cat_cfg["category"]
    slug = cat_cfg["slug"]

    # 1. DRINKS & BEVERAGES
    if cat == "Drinks & Beverages":
        if slug == "bier":
            return cat, "drinks_beer"
        if slug in ("weine", "schaumwein", "alkohlfreie-weine-schaumweine", "alkoholische-heissgetraenke"):
            return cat, "drinks_wine"
        if slug in ("spirituosen", "premixes"):
            return cat, "drinks_spirits"
        if slug == "kaffee":
            return cat, "drinks_coffee"
        if slug == "tee":
            return cat, "drinks_tea"
        if slug == "mineralwasser-soda":
            return cat, "drinks_water"
        if slug == "softdrinks-saefte":
            if any(w in n for w in ["saft", "nektar", "orange", "apfel", "multivitamin", "smoothie"]):
                return cat, "drinks_juice"
            return cat, "drinks_soda"
        if slug == "energy-drinks-eiskaffee":
            if any(w in n for w in ["eiskaffee", "cappuccino", "macchiato", "espresso"]):
                return cat, "drinks_coffee"
            return cat, "drinks_soda"
        return cat, cat_cfg["default_type"]

    # 2. DAIRY & EGGS
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

    # 3. FRESH PRODUCE
    if cat == "Fresh Produce":
        if any(w in n for w in ["apfel", "banane", "beere", "traube", "zitrone", "orange", "birne", "mango"]):
            return cat, "produce_fruit"
        if any(w in n for w in ["salat", "eisberg", "rucola", "spinat"]):
            return cat, "produce_salad"
        if any(w in n for w in ["petersilie", "basilikum", "schnittlauch", "kräuter"]):
            return cat, "produce_herbs"
        return cat, "produce_vegetable"

    # 4. MEAT & POULTRY (Cross-checks eggs and fish)
    if cat == "Meat & Poultry":
        if any(w in n for w in ["fisch", "lachs", "thunfisch", "forelle", "garnele"]):
            return "Fish & Seafood", "fish_fresh"
        if any(w in n for w in ["eier", "bodenhaltung", "freiland"]):
            return "Dairy & Eggs", "dairy_eggs"
        if any(w in n for w in ["huhn", "hähnchen", "pute", "geflügel"]):
            return cat, "meat_chicken"
        if any(w in n for w in ["rind", "faschiertes", "steak", "beiried"]):
            return cat, "meat_beef"
        if any(w in n for w in ["wurst", "schinken", "salami", "speck", "wiener"]):
            return cat, "meat_sausage"
        return cat, "meat_pork"

    # 5. BREAD & BAKERY
    if cat == "Bread & Bakery":
        if any(w in n for w in ["semmel", "weckerl", "brötchen", "kornspitz"]):
            return cat, "bakery_rolls"
        if any(w in n for w in ["torte", "kuchen", "muffin"]):
            return cat, "bakery_cake"
        if any(w in n for w in ["croissant", "plunder", "krapfen", "tasche"]):
            return cat, "bakery_pastry"
        return cat, "bakery_bread"

    # 6. FROZEN FOODS
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

    # 7. SNACKS & CONFECTIONERY
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

    # 8. PANTRY & BAKING
    if cat == "Pantry & Baking":
        if any(w in n for w in ["nudeln", "pasta", "spaghetti", "penne"]):
            return cat, "pantry_pasta"
        if any(w in n for w in ["reis"]):
            return cat, "pantry_rice"
        if any(w in n for w in ["öl", "essig", "olivenöl"]):
            return cat, "pantry_oil"
        if any(w in n for w in ["salz", "pfeffer", "gewürz", "oregano", "paprika"]):
            return cat, "pantry_spice"
        if any(w in n for w in ["mehl"]):
            return cat, "pantry_flour"
        if any(w in n for w in ["sauce", "pesto", "ketchup", "senf"]):
            return cat, "pantry_sauce"
        if any(w in n for w in ["dose", "bohnen", "mais"]):
            return cat, "pantry_canned"
        return cat, "pantry_baking"

    return cat, cat_cfg["default_type"]


def parse_product_card(card, cat_cfg: dict) -> dict:
    name1 = card.select_one(".product-tile__name1")
    name2 = card.select_one(".product-tile__name2")
    name3 = card.select_one(".product-tile__name3")

    brand_raw = name1.text.strip() if name1 else None
    item_title = name2.text.strip() if name2 else ""
    unit_raw = name3.text.strip() if name3 else ""

    full_name = f"{brand_raw or ''} {item_title}".strip() if item_title else (brand_raw or "Product")

    # Regular & Old Prices
    price_tag = card.select_one(".product-price__price")
    current_price = (
        price_tag.text.strip().replace(",", ".").replace("€", "") if price_tag else None
    )

    old_price_tag = card.select_one(".product-price__price-old")
    old_price = (
        old_price_tag.text.strip().replace("statt", "").replace(",", ".").replace("€", "").strip()
        if old_price_tag
        else None
    )

    # Download studio product image
    img_tag = card.select_one(".product-tile__image img") or card.select_one("img")
    image_url = None
    if img_tag:
        image_url = img_tag.get("data-src") or img_tag.get("src")
        if image_url:
            if image_url.startswith("//"):
                image_url = "https:" + image_url
            elif image_url.startswith("/"):
                image_url = "https://www.spar.at" + image_url

    local_image_path = download_image_locally(image_url, full_name)

    # Resolve category and product_type
    category, product_type = resolve_product_type_and_category(full_name, cat_cfg)

    # Detect Bio/Organic status from Spar badges
    is_organic = detect_spar_organic(card, full_name, brand_raw)

    return {
        "productName": full_name,
        "category": category,
        "productType": product_type,
        "brand": brand_raw,
        "packageSize": unit_raw,
        "currentPrice": current_price,
        "originalPrice": old_price,
        "remoteImageUrl": image_url,
        "localImagePath": local_image_path,
        "organic": is_organic,  # <-- Added: "yes" or "no"
    }


def setup_spar_location(driver, target_address):
    """Sets store location once on browser start."""
    js_cookie = f"""
    var host = document.getElementById('{SHADOW_ROOT_HOST_ID}');
    if (host && host.shadowRoot) {{
        var btn = host.shadowRoot.querySelector('{COOKIE_ACCEPT_SELECTOR}');
        if (btn) {{ btn.click(); return true; }}
    }}
    return false;
    """
    try:
        WebDriverWait(driver, 8).until(EC.presence_of_element_located((By.ID, SHADOW_ROOT_HOST_ID)))
        driver.execute_script(js_cookie)
        time.sleep(1)
    except Exception:
        pass

    try:
        store_btn = WebDriverWait(driver, 5).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, STORE_SELECT_BUTTON_SELECTOR))
        )
        driver.execute_script("arguments[0].click();", store_btn)

        search_input = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, SEARCH_INPUT_SELECTOR))
        )
        search_input.clear()
        search_input.send_keys(target_address)
        time.sleep(1.5)

        try:
            autocomplete = WebDriverWait(driver, 5).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, FIRST_AUTOCOMPLETE_ITEM_SELECTOR))
            )
            autocomplete.click()
        except TimeoutException:
            search_input.send_keys(Keys.ARROW_DOWN)
            time.sleep(0.5)
            search_input.send_keys(Keys.ENTER)

        WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.CSS_SELECTOR, LOCATION_LIST_PARENT)))
        time.sleep(1.5)

        parent = driver.find_element(By.CSS_SELECTOR, LOCATION_LIST_PARENT)
        options_list = parent.find_elements(By.CSS_SELECTOR, ALL_STORE_OPTIONS_SELECTOR)
        if options_list:
            btn = options_list[0].find_element(By.CSS_SELECTOR, STORE_BUTTON_RELATIVE_SELECTOR)
            driver.execute_script("arguments[0].click();", btn)

        WebDriverWait(driver, 10).until(EC.invisibility_of_element_located((By.CSS_SELECTOR, OVERLAY_WRAPPER_SELECTOR)))
        time.sleep(1)
        print("   -> Spar location set successfully. ✅")
    except Exception as e:
        print(f"   -> Warning setting location: {e}. Using default Spar store.")


def get_total_pages(driver) -> int:
    try:
        el = driver.find_element(By.CSS_SELECTOR, PAGINATION_TEXT_SELECTOR)
        match = re.search(r"von\s+(\d+)", el.text)
        return int(match.group(1)) if match else 1
    except NoSuchElementException:
        return 1


def main():
    driver = None
    all_scraped_products = []

    try:
        print("[1/3] Launching headless browser...")
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=options)

        # Set location on first category page
        initial_url = f"https://www.spar.at/produktwelt/{SPAR_CATEGORIES[0]['slug']}"
        print(f"[2/3] Setting store location via {initial_url}...")
        driver.get(initial_url)
        setup_spar_location(driver, TARGET_ADDRESS)

        print(f"\n[3/3] Crawling {len(SPAR_CATEGORIES)} Food & Drink Categories (max {MAX_PAGES_PER_CATEGORY} pages each)...")

        # --- OUTER LOOP: CATEGORIES ---
        for cat_idx, cat_cfg in enumerate(SPAR_CATEGORIES, start=1):
            base_cat_url = f"https://www.spar.at/produktwelt/{cat_cfg['slug']}"
            print(f"\n" + "=" * 60)
            print(f"[{cat_idx}/{len(SPAR_CATEGORIES)}] Scraping: {cat_cfg['category']} › {cat_cfg['slug']}")
            print(f"URL: {base_cat_url}")
            print("=" * 60)

            driver.get(base_cat_url)

            try:
                WebDriverWait(driver, WAIT_TIME_SECONDS).until(
                    EC.presence_of_element_located((By.ID, PRODUCT_GRID_ID))
                )
                total_cat_pages = get_total_pages(driver)
            except TimeoutException:
                total_cat_pages = 1

            pages_to_crawl = min(total_cat_pages, MAX_PAGES_PER_CATEGORY)

            # --- INNER LOOP: PAGES ---
            for page in range(1, pages_to_crawl + 1):
                page_url = f"{base_cat_url}?page={page}"
                print(f"  -> Page {page}/{pages_to_crawl} ({page_url})")

                if page > 1:
                    driver.get(page_url)
                    try:
                        WebDriverWait(driver, WAIT_TIME_SECONDS).until(
                            EC.presence_of_element_located((By.ID, PRODUCT_GRID_ID))
                        )
                    except TimeoutException:
                        break
                    time.sleep(1)

                soup = BeautifulSoup(driver.page_source, "html.parser")
                cards = soup.select(PRODUCT_CARD_SELECTOR)
                print(f"     Found {len(cards)} products.")

                for card in cards:
                    try:
                        product = parse_product_card(card, cat_cfg)
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
    bio_count = sum(1 for p in all_scraped_products if p.get("organic") == "yes")

    print("\n" + "=" * 60)
    print("SPAR SCRAPE COMPLETE SUMMARY:")
    print(f" • Total Products Scraped  : {len(all_scraped_products)}")
    print(f" • Bio / Organic Products   : {bio_count}")
    print(f" • Studio Photos Downloaded : {image_count}")
    print(f" • JSON Output Saved to     : {OUTPUT_JSON_PATH}")
    print(f" • Images Directory         : {IMAGE_DIR}/")
    print("=" * 60)


if __name__ == "__main__":
    main()