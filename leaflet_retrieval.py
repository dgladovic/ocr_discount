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
HOFER_FLYER_CARD_SELECTOR = '.cms-multilayout-teaser' 
HOFER_TITLE_SELECTOR = '.cms-multilayout-teaser__title' 
HOFER_DURATION_SELECTOR = '.cms-multilayout-teaser__description' 
HOFER_LINK_SELECTOR = '.cms-multilayout-teaser__link' 

def parse_hofer_dates(duration_str, current_year):
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
            "ViewerURL": result["URL"], 
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
        time.sleep(1)
    except:
        pass

    try:
        WebDriverWait(driver, WAIT_TIME_SECONDS).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, HOFER_FLYER_CARD_SELECTOR))
        )
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

            if title != "Flugblatt":
                continue
            
            duration_tag = card.select_one(HOFER_DURATION_SELECTOR)
            duration = duration_tag.text.strip() if duration_tag else "Duration N/A"

            link_tag = card.select_one(HOFER_LINK_SELECTOR)
            viewer_url = link_tag.get('href') if link_tag and link_tag.get('href') else "N/A"

            if viewer_url != "N/A":
                if viewer_url.startswith('/'):
                    viewer_url = "https://www.hofer.at" + viewer_url
                
                flyer_info = {
                    "Title": title, 
                    "URL": viewer_url,
                    "Duration": duration
                }
                scraped_data.append(flyer_info)

        relevant_flyer = find_most_relevant_flyer(scraped_data)
        
        if relevant_flyer:
            viewer_url = relevant_flyer.pop("ViewerURL")
            driver.get(viewer_url)
            
            try:
                pdf_button = WebDriverWait(driver, WAIT_TIME_SECONDS).until(
                    EC.presence_of_element_located((By.ID, "downloadAsPdf"))
                )
                relevant_flyer["PDF_URL"] = pdf_button.get_attribute("href")
                print(f"Hofer: Found direct PDF link.")
            except TimeoutException:
                relevant_flyer["PDF_URL"] = "N/A"
            
            print("--- Finished HOFER Scraping ---")
            return [relevant_flyer]

        print("--- Finished HOFER Scraping ---")
        return []

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

def find_most_relevant_spar_flyers(flyers_data):
    today = date.today()
    
    valid_flyers = []
    for f in flyers_data:
        if f.get('end_date_obj') and f['end_date_obj'] >= today:
            valid_flyers.append(f)
                
    main_flyers = []
    for f in valid_flyers:
        title_lower = f['Title'].lower()
        if 'flugblatt' in title_lower and 'sonderfolder' not in title_lower and 'magazin' not in title_lower:
            main_flyers.append(f)
            
    if not main_flyers and valid_flyers:
        main_flyers = valid_flyers
            
    retailer_flyers = {}
    for f in main_flyers:
        ret = f['Retailer']
        if ret not in retailer_flyers:
            retailer_flyers[ret] = []
        retailer_flyers[ret].append(f)
        
    final_results = []
    for ret, f_list in retailer_flyers.items():
        f_list.sort(key=lambda x: (x['end_date_obj'], x['start_date_obj']), reverse=True)
        best_flyer = f_list[0]
        
        final_results.append({
            "Title": best_flyer["Title"],
            "Retailer": best_flyer["Retailer"],
            "PDF_URL": best_flyer["PDF_URL"],
            "Duration": best_flyer["Duration"],
            "StartDate": best_flyer["StartDate"],
            "EndDate": best_flyer["EndDate"]
        })
        print(f"SPAR/INTERSPAR: Selected most relevant for {ret} -> {best_flyer['Title']}")
        
    return final_results

def scrape_spar(driver):
    print("--- Starting SPAR Scraping ---")
    scraped_data = []
    
    for url in SPAR_URLS:
        driver.get(url)
        try:
            WebDriverWait(driver, WAIT_TIME_SECONDS).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, 'article.flyer-teaser__teaser'))
            )
        except TimeoutException:
            continue
            
        html_content = driver.page_source
        soup = BeautifulSoup(html_content, 'html.parser')
        
        articles = soup.find_all('article', class_='flyer-teaser__teaser')
        
        for article in articles:
            classes = article.get('class', [])
            
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
                    base_ipaper_url = src.split('/Image.ashx')[0]
                    pdf_url = f"{base_ipaper_url}/pdf/Download.pdf"
                else:
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
                    "EndDate": end_date_str,
                    "start_date_obj": start_date_obj, 
                    "end_date_obj": end_date_obj
                }
                scraped_data.append(flyer_info)
                
    filtered_results = find_most_relevant_spar_flyers(scraped_data)
    
    print("--- Finished SPAR Scraping ---")
    return filtered_results


# =========================================================================
# === PENNY SCRAPER LOGIC ===
# =========================================================================

PENNY_URL = "https://www.penny.at/angebote/flugblaetter"

def parse_penny_dates(text_str, current_year):
    """
    Parses a German duration string like "Do 23.07. bis Mi 29.07.2026"
    Returns: (start_date_obj, end_date_obj)
    """
    matches = re.findall(r'(\d{1,2})\.(\d{1,2})\.(\d{4})?', text_str)
    
    if len(matches) >= 2:
        start_match = matches[0]
        end_match = matches[-1]
        
        try:
            end_year = int(end_match[2]) if end_match[2] else current_year
            end_date = date(end_year, int(end_match[1]), int(end_match[0]))
            
            start_year = int(start_match[2]) if start_match[2] else end_year
            start_date = date(start_year, int(start_match[1]), int(start_match[0]))
            
            # Handle cross-year (e.g., Dec 28 to Jan 3)
            if start_date > end_date:
                start_date = start_date.replace(year=end_date.year - 1)
                
            return start_date, end_date
        except ValueError:
            pass
            
    return None, None

def scrape_penny(driver):
    print("--- Starting PENNY Scraping ---")
    driver.get(PENNY_URL)
    
    # Accept cookies if applicable
    try:
        WebDriverWait(driver, 5).until(
            EC.element_to_be_clickable((By.ID, "onetrust-accept-btn-handler"))
        ).click()
        time.sleep(1)
    except:
        pass
        
    try:
        WebDriverWait(driver, WAIT_TIME_SECONDS).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, 'a.ws-image__wrapper'))
        )
    except TimeoutException:
        print("PENNY: Timeout waiting for flyer content to appear.")
        return []
        
    html_content = driver.page_source
    soup = BeautifulSoup(html_content, 'html.parser')
    
    links = soup.find_all('a', class_='ws-image__wrapper')
    scraped_data = []
    current_year = date.today().year
    
    for link in links:
        href = link.get('href', '')
        if 'issuu.com' not in href:
            continue
            
        aria_label = link.get('aria-label', '')
        
        # If aria-label doesn't contain text, fallback to parsing dates from href
        date_text = aria_label if aria_label else href
        
        start_date_obj, end_date_obj = parse_penny_dates(date_text, current_year)
        
        if start_date_obj and end_date_obj:
            flyer_info = {
                "Title": "PENNY Flugblatt",
                "Retailer": "PENNY",
                # Issuu does not expose direct static PDF links - we provide the viewer URL.
                "PDF_URL": href, 
                "Duration": aria_label if aria_label else "N/A",
                "StartDate": start_date_obj.strftime("%Y-%m-%d"),
                "EndDate": end_date_obj.strftime("%Y-%m-%d"),
                "start_date_obj": start_date_obj,
                "end_date_obj": end_date_obj
            }
            scraped_data.append(flyer_info)

    today = date.today()
    valid_flyers = [f for f in scraped_data if f['end_date_obj'] >= today]
    
    if valid_flyers:
        # Prioritize the flyer that spans furthest into the future (the current/upcoming one)
        valid_flyers.sort(key=lambda x: x['end_date_obj'], reverse=True)
        best_flyer = valid_flyers[0]
        
        # Cleanup
        del best_flyer['start_date_obj']
        del best_flyer['end_date_obj']
        
        print(f"PENNY: Found active flyer -> {best_flyer['Duration']}")
        print("--- Finished PENNY Scraping ---")
        return [best_flyer]
        
    print("PENNY: No active flyers found.")
    print("--- Finished PENNY Scraping ---")
    return []


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
        billa_results = scrape_billa(driver)
        all_flyers.extend(billa_results)
        
        # 3. Run Spar/Interspar Scraper
        spar_results = scrape_spar(driver)
        all_flyers.extend(spar_results)
        
        # 4. Run Penny Scraper
        penny_results = scrape_penny(driver)
        all_flyers.extend(penny_results)

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
        except Exception as e:
            print(f"ERROR: Could not save combined data to JSON file: {e}")
    else:
        print("\nNo relevant PDF links were scraped from either retailer. Skipping JSON save.")