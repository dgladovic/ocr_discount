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
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from bs4 import BeautifulSoup
from datetime import date, timedelta # Added timedelta

# --- CONFIGURATION ---
URL = "https://www.billa.at/unsere-aktionen/flugblatt"
OUTPUT_JSON_PATH = "billa_pdf_links.json"
WAIT_TIME_SECONDS = 15

# --- SELECTORS ---
# Selectors for the specific PDF buttons (based on aria-label attribute)
BILLA_PDF_LINK_SELECTOR = 'a[aria-label="BILLA Flugblatt als PDF downloaden"]'
BILLA_PLUS_PDF_LINK_SELECTOR = 'a[aria-label="BILLA PLUS Flugblatt als PDF downloaden"]'

# --- HEADLESS CHROME OPTIONS ---
options = webdriver.ChromeOptions()
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


def calculate_billa_duration_range():
    """
    Calculates the current BILLA flyer duration (Thursday to Wednesday) 
    based on the current date and formats the required German duration string.
    
    The cycle is: New flyer starts Thursday and ends the following Wednesday.
    Returns: (start_date_obj, end_date_obj, duration_string)
    """
    today = date.today()
    # ISO weekday: Monday=1, Tuesday=2, ..., Wednesday=3, Thursday=4, ..., Sunday=7
    iso_weekday = today.isoweekday() 
    
    # Thursday (ISO 4) is the start day of the cycle.
    
    # If today is Thursday, Friday, Saturday, or Sunday (iso_weekday >= 4), 
    # the start date is the current Thursday.
    if iso_weekday >= 4:
        # days_ago is the number of days since Thursday (e.g., Friday is 1 day ago)
        days_ago = iso_weekday - 4
        start_date = today - timedelta(days=days_ago)
    
    # If today is Monday, Tuesday, or Wednesday (iso_weekday < 4), 
    # the start date is the previous Thursday.
    else:
        # Days to subtract to reach the previous Thursday (e.g., Monday (1) must subtract 4 days)
        days_to_subtract = iso_weekday + 3 
        start_date = today - timedelta(days=days_to_subtract)
        
    # The end date is always 6 days after the start date (the following Wednesday).
    end_date = start_date + timedelta(days=6)

    # Format the required German string: VON DONNERSTAG, DD.MM. BIS MITTWOCH, DD.MM.YYYY
    duration_text = (
        f"VON DONNERSTAG, {start_date.day:02d}.{start_date.month:02d}. "
        f"BIS MITTWOCH, {end_date.day:02d}.{end_date.month:02d}.{end_date.year}"
    )
    
    return start_date, end_date, duration_text

def scrape_billa_pdf_links(url):
    """
    Scrapes the Billa flyer page for the current PDF download links and uses 
    calculated logic for the duration.
    """
    driver = None
    scraped_data = []
    
    try:
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=options)
    except Exception as e:
        print(f"Error initializing WebDriver: {e}")
        return []

    print(f"Navigating to {url}...")
    driver.get(url)
    
    # --- 1. WAIT FOR CONTENT TO LOAD ---
    try:
        # Wait until at least one of the main links is present
        WebDriverWait(driver, WAIT_TIME_SECONDS).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, BILLA_PDF_LINK_SELECTOR))
        )
        print("Flyer links loaded successfully.")
    except TimeoutException:
        print("Timeout waiting for flyer links to appear.")
        if driver:
             print("\nWebDriver kept open for debugging.")
        return []
    
    # --- 2. CALCULATE DURATION ---
    # The duration is calculated programmatically based on the known Thursday-to-Wednesday cycle.
    start_date, end_date, duration_text = calculate_billa_duration_range()
    print(f"Calculated Duration Range: {duration_text}")
    
    # --- 3. EXTRACT PDF LINKS ---
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
                "PDF_URL": pdf_url,
                "Duration": duration_text # Use the calculated duration
            }
            scraped_data.append(flyer_info)
            print(f"Found {title}: {pdf_url}")

        except NoSuchElementException:
            print(f"Warning: Could not find {title} link.")
            continue

    if driver:
        print("\nWebDriver kept open for debugging.")

    return scraped_data

if __name__ == "__main__":
    
    # 1. Run the scraper
    scraped_flyers = scrape_billa_pdf_links(URL)
    
    # 2. Save the data to the expected JSON file
    if scraped_flyers:
        try:
            with open(OUTPUT_JSON_PATH, 'w', encoding='utf-8') as f:
                json.dump(scraped_flyers, f, ensure_ascii=False, indent=2)
            print(f"\nSUCCESS: Scraped data saved to '{OUTPUT_JSON_PATH}'.")
        except Exception as e:
            print(f"ERROR: Could not save data to JSON file: {e}")
    else:
        print("\nNo relevant PDF links were scraped; skipping JSON save.")
