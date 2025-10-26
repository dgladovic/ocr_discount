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
import sys
from datetime import date # Added date import

# --- CONFIGURATION ---
URL = "https://www.hofer.at/de/angebote/aktuelle-flugblaetter-und-broschuren.html"
OUTPUT_JSON_PATH = "hofer_pdf_links.json"
WAIT_TIME_SECONDS = 15
TARGET_FLYER_TITLE = "Blättern Sie online im HOFER Flugblatt" # Constant for filtering

# --- SELECTORS ---
COOKIE_ACCEPT_ID = "onetrust-accept-btn-handler" 
FLYER_CARD_SELECTOR = '.item.card_leaflet' 
FLYER_TITLE_SELECTOR = '.card-title' 
FLYER_DURATION_SELECTOR = '.card_leaflet__content p' 
PDF_LINK_SELECTOR = 'a.btn-invisible.text-left' 

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


def parse_german_date(duration_str, current_year):
    """
    Parses a German duration string (e.g., '... bis Donnerstag, 30.10.2025') 
    to extract the end date as a date object.
    """
    # Regex to find all date components (DD.MM.YYYY or DD.MM.)
    # The last match will always correspond to the End Date.
    match_dates = re.findall(r'(\d{1,2})\.(\d{1,2})\.?(\d{4})?', duration_str)
    
    if match_dates:
        # Get the very last matched date components
        day_str, month_str, year_str = match_dates[-1]
        
        # If year is missing (e.g., '17.10.'), use the provided year
        year = int(year_str) if year_str else current_year 
        
        try:
            return date(int(year), int(month_str), int(day_str))
        except ValueError:
            return None
            
    return None

def find_most_relevant_flyer(flyers_data):
    """
    Analyzes all scraped Hofer flyers and determines the single most relevant one
    based on the current date (today). Prioritizes the next upcoming or current flyer.
    """
    today = date.today()
    parsed_flyers = []

    # 1. Parse end dates for all flyers
    current_year = today.year
    for flyer in flyers_data:
        end_date = parse_german_date(flyer['Duration'], current_year)
        
        if end_date:
            flyer['end_date'] = end_date
            
            # Adjust year for year-end turnover (e.g., Dec flyer ending in Jan)
            if end_date < today and today.month == 12 and end_date.month == 1:
                end_date = parse_german_date(flyer['Duration'], current_year + 1)
                if end_date:
                    flyer['end_date'] = end_date
            
            parsed_flyers.append(flyer)


    # 2. Filtering Logic: Find the flyer that ends furthest in the future (most current/upcoming)
    
    # A. Find all flyers that are CURRENT or UPCOMING (end date >= today)
    upcoming_or_current = [f for f in parsed_flyers if f['end_date'] >= today]
    
    if upcoming_or_current:
        # Choose the one that ends furthest in the future (the newest and most relevant)
        upcoming_or_current.sort(key=lambda x: x['end_date'], reverse=True)
        # Prepare result, removing the internal 'end_date' field
        result = upcoming_or_current[0].copy()
        del result['end_date']
        return result
    
    # B. Fallback: If no flyers are current/upcoming (we ran late), return the one that expired most recently.
    if parsed_flyers:
        # Sort by end date descending (most recent expired first)
        parsed_flyers.sort(key=lambda x: x['end_date'], reverse=True)
        result = parsed_flyers[0].copy()
        del result['end_date']
        print(f"Warning: All flyers are expired as of {today}. Returning the most recently expired flyer.")
        return result
        
    return None

def scrape_hofer_pdf_links(url):
    """
    Scrapes Hofer's flyer page for all main PDF download links and titles, 
    and extracts the duration of the deals, returning a list of all matches.
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
    
    # --- 1. HANDLE COOKIE BANNER ---
    try:
        WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.ID, COOKIE_ACCEPT_ID))
        ).click()
        print("Cookie banner accepted.")
        time.sleep(1) 
    except TimeoutException:
        print("No cookie banner found or timed out.")
        pass
    except NoSuchElementException:
        print("Cookie acceptance button not found by ID. Proceeding.")
        pass

    # --- 2. WAIT FOR FLYER CONTENT TO LOAD ---
    try:
        WebDriverWait(driver, WAIT_TIME_SECONDS).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, FLYER_CARD_SELECTOR))
        )
        print("Flyer container loaded successfully.")
    except TimeoutException:
        print("Timeout waiting for flyer content to appear.")
        return []

    # --- 3. FINAL SCRAPE AND PARSE ---
    try:
        print("\nStarting final HTML parsing with BeautifulSoup...")
        html_content = driver.page_source
        soup = BeautifulSoup(html_content, 'html.parser')

        flyer_cards = soup.select(FLYER_CARD_SELECTOR)
        
        for i, card in enumerate(flyer_cards):
            
            # Extract Title
            title_tag = card.select_one(FLYER_TITLE_SELECTOR)
            title = title_tag.text.strip() if title_tag else f"Flyer {i+1} (Title N/A)"

            # Filter: Only collect if the title matches the specific Hofer flyer
            if title != TARGET_FLYER_TITLE:
                continue
            
            # Extract Duration/Validity Dates
            duration_tag = card.select_one(FLYER_DURATION_SELECTOR)
            duration = duration_tag.text.strip() if duration_tag else "Duration N/A"

            # Extract PDF Link
            pdf_link_tag = card.select_one(PDF_LINK_SELECTOR)
            pdf_url = pdf_link_tag.get('href') if pdf_link_tag and pdf_link_tag.get('href') else "N/A"

            if pdf_url != "N/A":
                # Make Hofer URLs absolute
                if pdf_url.startswith('/'):
                    pdf_url = "https://www.hofer.at" + pdf_url
                
                flyer_info = {
                    "Title": title, 
                    "PDF_URL": pdf_url,
                    "Duration": duration
                }
                scraped_data.append(flyer_info)
            else:
                print(f"Warning: No PDF link found for flyer: {title}")


        print(f"\nSuccessfully collected {len(scraped_data)} potential PDF flyers for the target title.")
        return scraped_data

    except Exception as e:
        print(f"\nAn error occurred during final parsing: {e}")
        return []
    finally:
        if driver:
            # driver.quit() 
            print("\nWebDriver kept open as requested.")
        else:
            print("\nWebDriver was not initialized.")


if __name__ == "__main__":
    
    # 1. Run the scraper and get ALL matching flyers
    scraped_flyers = scrape_hofer_pdf_links(URL)
    
    # 2. Filter to find the MOST RELEVANT one based on the current date
    relevant_flyer = find_most_relevant_flyer(scraped_flyers)
    
    # 3. Save only the relevant flyer data
    if relevant_flyer:
        # Save as a list containing a single object for consistency
        data_to_save = [relevant_flyer] 
        try:
            with open(OUTPUT_JSON_PATH, 'w', encoding='utf-8') as f:
                json.dump(data_to_save, f, ensure_ascii=False, indent=2)
            print(f"\nSUCCESS: Most relevant flyer data saved to '{OUTPUT_JSON_PATH}'.")
        except Exception as e:
            print(f"ERROR: Could not save data to JSON file: {e}")
    else:
        print("\nNo relevant PDF links were found; skipping JSON save.")
