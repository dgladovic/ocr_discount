import os
import json
import re 
import time 
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from bs4 import BeautifulSoup
from datetime import date, timedelta

# --- GLOBAL CONFIGURATION ---
WAIT_TIME_SECONDS = 15
# This file will be OVERWRITTEN daily to provide the latest snapshot
OUTPUT_JSON_PATH = "current_active_flyers.json" 
TARGET_HOFER_TITLE = "Blättern Sie online im HOFER Flugblatt" 

# --- HEADLESS CHROME OPTIONS ---
options = webdriver.ChromeOptions()
options.add_argument('--headless=new') # Commented out for easier debugging
options.add_argument('--no-sandbox')
options.add_argument('--disable-dev-shm-usage')
options.add_argument('--window-size=1920,1080')
options.add_argument('user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36')
options.add_experimental_option("excludeSwitches", ["enable-automation"]) 
options.add_experimental_option('useAutomationExtension', False)
options.add_argument('--disable-gpu')
options.add_argument('--disable-logging')
options.add_argument('--log-level=3') 


# =========================================================================
# === HOFER SCRAPER LOGIC ===
# =========================================================================

HOFER_URL = "https://www.hofer.at/de/angebote/aktuelle-flugblaetter-und-broschuren.html"
HOFER_COOKIE_ACCEPT_ID = "onetrust-accept-btn-handler" 
HOFER_FLYER_CARD_SELECTOR = '.item.card_leaflet' 
HOFER_TITLE_SELECTOR = '.card-title' 
HOFER_DURATION_SELECTOR = '.card_leaflet__content p' 
HOFER_PDF_LINK_SELECTOR = 'a.btn-invisible.text-left' 

def parse_hofer_dates(duration_str, current_year):
    """
    Parses a German duration string to extract the start and end dates.
    Returns: (start_date_obj, end_date_obj)
    """
    # Regex to find all date components (DD.MM.YYYY or DD.MM.)
    match_dates = re.findall(r'(\d{1,2})\.(\d{1,2})\.?(\d{4})?', duration_str)
    
    if not match_dates:
        return None, None
    
    dates = []
    for day_str, month_str, year_str in match_dates:
        year = int(year_str) if year_str else current_year 
        
        try:
            current_date = date(int(year), int(month_str), int(day_str))
            dates.append(current_date)
        except ValueError:
            continue
            
    if not dates:
        return None, None

    # The FIRST date found is typically the start date.
    start_date = dates[0]
    # The LAST date found is typically the end date.
    end_date = dates[-1]
    
    # Handle year turnover (e.g., Dec start, Jan end)
    if end_date < start_date and end_date.month < start_date.month:
        end_date = end_date.replace(year=end_date.year + 1)
        
    return start_date, end_date

def find_most_relevant_flyer(flyers_data):
    """
    Analyzes all scraped Hofer flyers and determines the single most relevant one
    based on the current date (today).
    """
    today = date.today()
    parsed_flyers = []

    # 1. Parse dates and apply year turnover logic
    current_year = today.year
    for flyer in flyers_data:
        start_date, end_date = parse_hofer_dates(flyer['Duration'], current_year)
        
        if end_date and start_date:
            flyer['end_date_obj'] = end_date
            flyer['start_date_obj'] = start_date
            parsed_flyers.append(flyer)

    # 2. Filtering Logic: Find the flyer that is current (end date >= today)
    upcoming_or_current = [f for f in parsed_flyers if f['end_date_obj'] >= today]
    
    result = None
    if upcoming_or_current:
        # Choose the one that ends furthest in the future (the newest/most relevant cycle)
        upcoming_or_current.sort(key=lambda x: x['end_date_obj'], reverse=True)
        result = upcoming_or_current[0]
    elif parsed_flyers:
        # Fallback: If no flyers are current, return the one that expired most recently.
        parsed_flyers.sort(key=lambda x: x['end_date_obj'], reverse=True)
        print(f"Warning: All Hofer flyers appear expired as of {today}. Returning the most recently expired flyer.")
        result = parsed_flyers[0]
        
    if result:
        # Format the final output structure
        return {
            "Title": result["Title"],
            "Retailer": "HOFER",
            "PDF_URL": result["PDF_URL"],
            # Original German duration string for reference
            "Duration": result["Duration"], 
            # Parsed dates in standard YYYY-MM-DD format
            "StartDate": result["start_date_obj"].strftime("%Y-%m-%d"), 
            "EndDate": result["end_date_obj"].strftime("%Y-%m-%d")
        }
    
    return None

def scrape_hofer(driver):
    """Scrapes Hofer's flyer page for the most relevant PDF link."""
    print("--- Starting HOFER Scraping ---")
    driver.get(HOFER_URL)
    
    # --- 1. HANDLE COOKIE BANNER ---
    try:
        WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.ID, HOFER_COOKIE_ACCEPT_ID))
        ).click()
        print("Hofer: Cookie banner accepted.")
        time.sleep(1)
    except TimeoutException:
        print("Hofer: No cookie banner found or timed out.")
    except Exception as e:
        print(f"Hofer: Error during cookie handling: {e}. Proceeding.")

    # --- 2. WAIT FOR FLYER CONTENT TO LOAD ---
    try:
        WebDriverWait(driver, WAIT_TIME_SECONDS).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, HOFER_FLYER_CARD_SELECTOR))
        )
        print("Hofer: Flyer container loaded successfully.")
    except TimeoutException:
        print("Hofer: Timeout waiting for flyer content to appear.")
        return []

    # --- 3. SCRAPE AND PARSE WITH BEAUTIFULSOUP ---
    scraped_data = []
    try:
        html_content = driver.page_source
        soup = BeautifulSoup(html_content, 'html.parser')

        flyer_cards = soup.select(HOFER_FLYER_CARD_SELECTOR)
        
        for card in flyer_cards:
            title_tag = card.select_one(HOFER_TITLE_SELECTOR)
            title = title_tag.text.strip() if title_tag else "Title N/A"

            if title != TARGET_HOFER_TITLE:
                continue
            
            duration_tag = card.select_one(HOFER_DURATION_SELECTOR)
            duration = duration_tag.text.strip() if duration_tag else "Duration N/A"

            pdf_link_tag = card.select_one(HOFER_PDF_LINK_SELECTOR)
            pdf_url = pdf_link_tag.get('href') if pdf_link_tag and pdf_link_tag.get('href') else "N/A"

            if pdf_url != "N/A":
                if pdf_url.startswith('/'):
                    pdf_url = "https://www.hofer.at" + pdf_url
                
                flyer_info = {
                    "Title": title, 
                    "PDF_URL": pdf_url,
                    "Duration": duration
                }
                scraped_data.append(flyer_info)

        relevant_flyer = find_most_relevant_flyer(scraped_data)
        
        print("--- Finished HOFER Scraping ---")
        return [relevant_flyer] if relevant_flyer else []

    except Exception as e:
        print(f"\nHofer: An error occurred during final parsing: {e}")
        return []


# =========================================================================
# === BILLA SCRAPER LOGIC ===
# =========================================================================

BILLA_URL = "https://www.billa.at/unsere-aktionen/flugblatt"
BILLA_PDF_LINK_SELECTOR = 'a[aria-label="BILLA Flugblatt als PDF downloaden"]'
BILLA_PLUS_PDF_LINK_SELECTOR = 'a[aria-label="BILLA PLUS Flugblatt als PDF downloaden"]'

def calculate_billa_duration_range():
    """
    Calculates the current BILLA flyer duration (Thursday to Wednesday) 
    based on the current date.
    Returns: (start_date_obj, end_date_obj, duration_string)
    """
    today = date.today()
    iso_weekday = today.isoweekday() 
    
    # Thursday (ISO 4) is the start day of the cycle.
    if iso_weekday >= 4:
        # Today is Thu, Fri, Sat, or Sun. Start date is the current Thursday.
        days_ago = iso_weekday - 4
        start_date = today - timedelta(days=days_ago)
    else:
        # Today is Mon, Tue, or Wed. Start date is the previous Thursday.
        days_to_subtract = iso_weekday + 3 
        start_date = today - timedelta(days=days_to_subtract)
        
    end_date = start_date + timedelta(days=6)

    # Format the original German string
    duration_text = (
        f"VON DONNERSTAG, {start_date.day:02d}.{start_date.month:02d}. "
        f"BIS MITTWOCH, {end_date.day:02d}.{end_date.month:02d}.{end_date.year}"
    )
    
    return start_date, end_date, duration_text

def scrape_billa(driver):
    """Scrapes the Billa flyer page for the current PDF download links and includes the calculated duration dates."""
    print("--- Starting BILLA Scraping ---")
    driver.get(BILLA_URL)
    scraped_data = []
    
    try:
        WebDriverWait(driver, WAIT_TIME_SECONDS).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, BILLA_PDF_LINK_SELECTOR))
        )
        print("BILLA Flyer links loaded successfully.")
    except TimeoutException:
        print("BILLA: Timeout waiting for flyer links to appear.")
        return []
    
    # --- CALCULATE DURATION ---
    start_date_obj, end_date_obj, duration_text = calculate_billa_duration_range()
    
    # --- EXTRACT PDF LINKS ---
    flyer_selectors = [
        ("BILLA Flugblatt", BILLA_PDF_LINK_SELECTOR),
        ("BILLA PLUS Flugblatt", BILLA_PLUS_PDF_LINK_SELECTOR)
    ]
    
    for title, selector in flyer_selectors:
        try:
            pdf_link_tag = driver.find_element(By.CSS_SELECTOR, selector)
            pdf_url = pdf_link_tag.get_attribute('href')
            
            flyer_info = {
                "Title": title,
                "Retailer": "BILLA",
                "PDF_URL": pdf_url,
                # Original German duration string for reference
                "Duration": duration_text, 
                # Parsed dates in standard YYYY-MM-DD format
                "StartDate": start_date_obj.strftime("%Y-%m-%d"), 
                "EndDate": end_date_obj.strftime("%Y-%m-%d")
            }
            scraped_data.append(flyer_info)
            print(f"BILLA: Found {title}")

        except NoSuchElementException:
            print(f"BILLA: Warning: Could not find {title} link.")
            continue
            
    print("--- Finished BILLA Scraping ---")
    return scraped_data


# =========================================================================
# === MAIN EXECUTION ===
# =========================================================================

if __name__ == "__main__":
    driver = None
    all_flyers = []
    
    try:
        # Initialize the WebDriver once
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=options)
        
        # 1. Run Hofer Scraper
        hofer_results = scrape_hofer(driver)
        all_flyers.extend(hofer_results)

        # 2. Run Billa Scraper
        billa_results = scrape_billa(driver)
        all_flyers.extend(billa_results)

    except Exception as e:
        print(f"\nCRITICAL ERROR during script execution: {e}")
        if driver:
             print("\nWebDriver kept open for debugging on critical error.")

    finally:
        # Quit driver only if it hasn't been kept open due to critical failure
        if driver and 'CRITICAL ERROR' not in locals():
            # driver.quit() # Keep open as requested for general inspection
            print("\nFinal WebDriver kept open for inspection.")
    
    # 3. Save the combined data, overwriting the previous file
    if all_flyers:
        try:
            # Use 'w' mode to OVERWRITE the file with the current set of active flyers
            with open(OUTPUT_JSON_PATH, 'w', encoding='utf-8') as f:
                json.dump(all_flyers, f, ensure_ascii=False, indent=2)
            print(f"\nSUCCESS: Combined data for {len(all_flyers)} flyers saved to '{OUTPUT_JSON_PATH}'.")
            print("NOTE: This file is overwritten daily to ensure the list is current.")
        except Exception as e:
            print(f"ERROR: Could not save combined data to JSON file: {e}")
    else:
        print("\nNo relevant PDF links were scraped from either retailer. Skipping JSON save.")
