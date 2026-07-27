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
# options.add_argument('--headless=new') # Commented out for easier debugging
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

    start_date = dates[0]
    end_date = dates[-1]
    
    if end_date < start_date and end_date.month < start_date.month:
        end_date = end_date.replace(year=end_date.year + 1)
        
    return start_date, end_date

def find_most_relevant_flyer(flyers_data):
    today = date.today()
    parsed_flyers = []

    current_year = today.year
    for flyer in flyers_data:
        start_date, end_date = parse_hofer_dates(flyer['Duration'], current_year)
        
        if end_date and start_date:
            flyer['end_date_obj'] = end_date
            flyer['start_date_obj'] = start_date
            parsed_flyers.append(flyer)

    upcoming_or_current = [f for f in parsed_flyers if f['end_date_obj'] >= today]
    
    result = None
    if upcoming_or_current:
        upcoming_or_current.sort(key=lambda x: x['end_date_obj'], reverse=True)
        result = upcoming_or_current[0]
    elif parsed_flyers:
        parsed_flyers.sort(key=lambda x: x['end_date_obj'], reverse=True)
        print(f"Warning: All Hofer flyers appear expired as of {today}. Returning the most recently expired flyer.")
        result = parsed_flyers[0]
        
    if result:
        return {
            "Title": result["Title"],
            "Retailer": "HOFER",
            "PDF_URL": result["PDF_URL"],
            "Duration": result["Duration"], 
            "StartDate": result["start_date_obj"].strftime("%Y-%m-%d"), 
            "EndDate": result["end_date_obj"].strftime("%Y-%m-%d")
        }
    
    return None

def scrape_hofer(driver):
    print("--- Starting HOFER Scraping ---")
    driver.get(HOFER_URL)
    
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

    try:
        WebDriverWait(driver, WAIT_TIME_SECONDS).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, HOFER_FLYER_CARD_SELECTOR))
        )
        print("Hofer: Flyer container loaded successfully.")
    except TimeoutException:
        print("Hofer: Timeout waiting for flyer content to appear.")
        return []

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
    today = date.today()
    iso_weekday = today.isoweekday() 
    
    if iso_weekday >= 4:
        days_ago = iso_weekday - 4
        start_date = today - timedelta(days=days_ago)
    else:
        days_to_subtract = iso_weekday + 3 
        start_date = today - timedelta(days=days_to_subtract)
        
    end_date = start_date + timedelta(days=6)

    duration_text = (
        f"VON DONNERSTAG, {start_date.day:02d}.{start_date.month:02d}. "
        f"BIS MITTWOCH, {end_date.day:02d}.{end_date.month:02d}.{end_date.year}"
    )
    
    return start_date, end_date, duration_text

def scrape_billa(driver):
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
    
    start_date_obj, end_date_obj, duration_text = calculate_billa_duration_range()
    
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
                "Duration": duration_text, 
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
# === SPAR SCRAPER LOGIC ===
# =========================================================================

SPAR_URLS = [
    "https://www.spar.at/aktionen/wien/spar",
    "https://www.spar.at/aktionen/wien/interspar"
]

def parse_spar_dates(duration_str):
    """
    Parses a German duration string from Spar to extract the start and end dates.
    Matches formats like 'Do., 23.07.26 - Mi., 29.07.26'.
    Returns: (start_date_obj, end_date_obj)
    """
    if not duration_str:
        return None, None
        
    matches = re.findall(r'(\d{1,2})\.(\d{1,2})\.(\d{2,4})', duration_str)
    
    if len(matches) >= 2:
        start_match = matches[0]
        end_match = matches[-1]
        
        try:
            start_year = int(start_match[2])
            if start_year < 100: 
                start_year += 2000
            start_date = date(start_year, int(start_match[1]), int(start_match[0]))
            
            end_year = int(end_match[2])
            if end_year < 100: 
                end_year += 2000
            end_date = date(end_year, int(end_match[1]), int(end_match[0]))
            
            return start_date, end_date
        except ValueError:
            pass
            
    return None, None

def scrape_spar(driver):
    """Scrapes SPAR and INTERSPAR flyer pages for the current active PDF links."""
    print("--- Starting SPAR Scraping ---")
    scraped_data = []
    
    for url in SPAR_URLS:
        print(f"SPAR: Navigating to {url}")
        driver.get(url)
        
        try:
            WebDriverWait(driver, WAIT_TIME_SECONDS).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, 'article.flyer-teaser__teaser'))
            )
            print(f"SPAR: Flyer container loaded successfully for {url}.")
        except TimeoutException:
            print(f"SPAR: Timeout waiting for flyer content to appear on {url}.")
            continue
            
        html_content = driver.page_source
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # Select all flyers rendered in the HTML
        articles = soup.find_all('article', class_='flyer-teaser__teaser')
        
        for article in articles:
            classes = article.get('class', [])
            
            # The webpage marks visible articles (rendered to the user) with `--active`
            if 'flyer-teaser__teaser--active' not in classes:
                continue
                
            title_tag = article.select_one('.flyer-teaser__caption')
            title = title_tag.text.strip() if title_tag else "Title N/A"
            
            duration_tag = article.select_one('.flyer-teaser__valid')
            duration = duration_tag.text.strip() if duration_tag else "Duration N/A"
            
            link_tag = article.select_one('a.flyer-teaser__teaser-inner')
            href = link_tag.get('href') if link_tag else None
            
            retailer = article.get('data-type', 'SPAR').strip()
            
            if href:
                img_tag = article.select_one('img.flyer-teaser__image')
                if img_tag and img_tag.get('src'):
                    src = img_tag.get('src')
                    # e.g., https://flugblatt.spar.at/wien/spar/260723-1-flugblatt-kw-30/Image.ashx?...
                    base_ipaper_url = src.split('/Image.ashx')[0]
                    # Direct PDF download link format for iPaper
                    pdf_url = f"{base_ipaper_url}/pdf/Download.pdf"
                else:
                    # Fallback to the web viewer URL
                    pdf_url = f"https://www.spar.at{href}"
                    
                start_date_obj, end_date_obj = parse_spar_dates(duration)
                start_date_str = start_date_obj.strftime("%Y-%m-%d") if start_date_obj else "N/A"
                end_date_str = end_date_obj.strftime("%Y-%m-%d") if end_date_obj else "N/A"
                
                flyer_info = {
                    "Title": title,
                    "Retailer": retailer,
                    "PDF_URL": pdf_url,
                    "Duration": duration,
                    "StartDate": start_date_str,
                    "EndDate": end_date_str
                }
                scraped_data.append(flyer_info)
                print(f"SPAR: Found active flyer '{title}' for {retailer}")
                
    print("--- Finished SPAR Scraping ---")
    return scraped_data


# =========================================================================
# === MAIN EXECUTION ===
# =========================================================================

if __name__ == "__main__":
    driver = None
    all_flyers = []
    
    try:
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=options)
        
        # 1. Run Hofer Scraper
        hofer_results = scrape_hofer(driver)
        all_flyers.extend(hofer_results)

        # 2. Run Billa Scraper
        # billa_results = scrape_billa(driver)
        # all_flyers.extend(billa_results)
        
        # 3. Run Spar/Interspar Scraper
        # spar_results = scrape_spar(driver)
        # all_flyers.extend(spar_results)

    except Exception as e:
        print(f"\nCRITICAL ERROR during script execution: {e}")
        if driver:
             print("\nWebDriver kept open for debugging on critical error.")

    finally:
        if driver and 'CRITICAL ERROR' not in locals():
            print("\nFinal WebDriver kept open for inspection.")
    
    # Save the combined data, overwriting the previous file
    if all_flyers:
        try:
            with open(OUTPUT_JSON_PATH, 'w', encoding='utf-8') as f:
                json.dump(all_flyers, f, ensure_ascii=False, indent=2)
            print(f"\nSUCCESS: Combined data for {len(all_flyers)} flyers saved to '{OUTPUT_JSON_PATH}'.")
            print("NOTE: This file is overwritten daily to ensure the list is current.")
        except Exception as e:
            print(f"ERROR: Could not save combined data to JSON file: {e}")
    else:
        print("\nNo relevant PDF links were scraped from either retailer. Skipping JSON save.")