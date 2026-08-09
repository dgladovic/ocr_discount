import os
import json
import re 
import time 
import urllib.parse
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
OUTPUT_JSON_PATH = "current_active_flyers.json" 
DOWNLOAD_DIR = os.path.abspath("downloads")
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

# --- HEADLESS CHROME OPTIONS ---
options = webdriver.ChromeOptions()
options.add_argument('--headless=new') 
options.add_argument('--no-sandbox')
options.add_argument('--disable-dev-shm-usage')
options.add_argument('--window-size=1920,1080')
options.add_argument('user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36')
options.add_experimental_option("excludeSwitches", ["enable-automation"]) 
options.add_experimental_option('useAutomationExtension', False)
options.add_argument('--disable-gpu')
options.add_argument('--disable-logging')
options.add_argument('--log-level=3') 

# Enable direct PDF downloading inside Headless Chrome
chrome_prefs = {
    "download.default_directory": DOWNLOAD_DIR,
    "download.prompt_for_download": False,
    "download.directory_upgrade": True,
    "plugins.always_open_pdf_externally": True
}
options.add_experimental_option("prefs", chrome_prefs)


# =========================================================================
# === HELPER FUNCTIONS ===
# =========================================================================

def slugify(text):
    """Generates the same safe filename slug as leaflet_downloader.py."""
    text = str(text).lower().strip()
    text = re.sub(r'[^\w\s-]', '', text)
    text = re.sub(r'[-\s]+', '', text)
    return text[:50]

def get_pdf_url_via_click(driver, viewer_url, button_selector):
    """
    Navigates to the viewer URL, intercepts dynamic JS download behavior,
    clicks the specified button, and captures the raw PDF URL (used for Penny/Hofer).
    """
    print(f"   -> Navigating to viewer: {viewer_url}")
    driver.get(viewer_url)
    time.sleep(2)
    
    driver.execute_script("""
        window.__captured_pdf = null;
        window.open = function(url) { window.__captured_pdf = url; return null; };
        var origClick = HTMLAnchorElement.prototype.click;
        HTMLAnchorElement.prototype.click = function() { if (this.href) { window.__captured_pdf = this.href; } };
        window.location.assign = function(url) { window.__captured_pdf = url; };
        window.location.replace = function(url) { window.__captured_pdf = url; };
        var origAppend = Element.prototype.appendChild;
        Element.prototype.appendChild = function(child) {
            if (child.tagName === 'IFRAME' && child.src) { window.__captured_pdf = child.src; }
            return origAppend.apply(this, arguments);
        };
    """)
    
    try:
        btn = WebDriverWait(driver, 10).until(EC.element_to_be_clickable((By.CSS_SELECTOR, button_selector)))
        try: btn.click()
        except: driver.execute_script("arguments[0].click();", btn)
            
        print("   -> Download triggered. Intercepting URL request...")
        for _ in range(20):
            time.sleep(0.5)
            pdf_url = driver.execute_script("return window.__captured_pdf;")
            if pdf_url:
                if pdf_url.startswith('/'):
                    parsed = urllib.parse.urlparse(driver.current_url)
                    pdf_url = f"{parsed.scheme}://{parsed.netloc}{pdf_url}"
                print("   -> Success! Direct PDF URL intercepted.")
                return pdf_url
    except Exception as e:
        print(f"   -> Error extracting PDF via JS: {e}")
        
    return None

def download_spar_pdf_via_selenium(driver, ipaper_url, target_filepath):
    """
    Navigates directly to the iPaper viewer page, clicks #modDownloadPdfBtn,
    waits for Chrome to download the PDF, and renames it to the target filename.
    """
    print(f"   -> Navigating directly to iPaper viewer: {ipaper_url}")
    driver.get(ipaper_url)
    
    try:
        btn = WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.ID, "modDownloadPdfBtn"))
        )
    except TimeoutException:
        print(f"   -> ERROR: #modDownloadPdfBtn not found on {ipaper_url}")
        return False

    files_before = set(os.listdir(DOWNLOAD_DIR))
    
    print("   -> Clicking PDF download button in Spar viewer...")
    try:
        btn.click()
    except:
        driver.execute_script("arguments[0].click();", btn)
        
    print("   -> Waiting for browser to download PDF...")
    downloaded_filename = None
    
    # Poll for up to 15 seconds for new file to complete downloading
    for _ in range(30):
        time.sleep(0.5)
        files_after = set(os.listdir(DOWNLOAD_DIR))
        new_files = files_after - files_before
        
        completed_pdfs = [f for f in new_files if f.lower().endswith('.pdf') and not f.lower().endswith('.crdownload') and not f.lower().endswith('.tmp')]
        if completed_pdfs:
            downloaded_filename = completed_pdfs[0]
            break
            
    if downloaded_filename:
        src_path = os.path.join(DOWNLOAD_DIR, downloaded_filename)
        if os.path.exists(target_filepath):
            os.remove(target_filepath)
        os.rename(src_path, target_filepath)
        print(f"   -> SUCCESS: Directly saved Spar PDF to: {target_filepath}")
        return True
    else:
        print("   -> ERROR: Timed out waiting for Spar PDF download to finish.")
        return False


# =========================================================================
# === HOFER SCRAPER LOGIC ===
# =========================================================================

HOFER_URL = "https://www.hofer.at/de/angebote/aktuelle-flugblaetter-und-broschuren.html"
HOFER_FLYER_CARD_SELECTOR = '.cms-multilayout-teaser' 
HOFER_TITLE_SELECTOR = '.cms-multilayout-teaser__title' 
HOFER_DURATION_SELECTOR = '.cms-multilayout-teaser__description' 
HOFER_LINK_SELECTOR = '.cms-multilayout-teaser__link' 

def parse_hofer_dates(duration_str, current_year):
    match_dates = re.findall(r'(\d{1,2})\.(\d{1,2})\.?(\d{4})?', duration_str)
    if not match_dates: return None, None
    dates = []
    for day_str, month_str, year_str in match_dates:
        year = int(year_str) if year_str else current_year 
        try: dates.append(date(int(year), int(month_str), int(day_str)))
        except ValueError: continue
            
    if not dates: return None, None
    start_date, end_date = dates[0], dates[-1]
    if end_date < start_date and end_date.month < start_date.month:
        end_date = end_date.replace(year=end_date.year + 1)
    return start_date, end_date

def scrape_hofer(driver):
    print("\n--- Starting HOFER Scraping ---")
    driver.get(HOFER_URL)
    
    try:
        WebDriverWait(driver, 5).until(EC.element_to_be_clickable((By.ID, "onetrust-accept-btn-handler"))).click()
        time.sleep(1)
    except: pass

    try:
        WebDriverWait(driver, WAIT_TIME_SECONDS).until(EC.presence_of_element_located((By.CSS_SELECTOR, HOFER_FLYER_CARD_SELECTOR)))
    except TimeoutException:
        print("Hofer: Timeout waiting for flyer content to appear.")
        return []

    scraped_data = []
    soup = BeautifulSoup(driver.page_source, 'html.parser')
    
    for card in soup.select(HOFER_FLYER_CARD_SELECTOR):
        title_tag = card.select_one(HOFER_TITLE_SELECTOR)
        title = title_tag.text.strip() if title_tag else ""
        if title != "Flugblatt": continue
        
        duration_tag = card.select_one(HOFER_DURATION_SELECTOR)
        link_tag = card.select_one(HOFER_LINK_SELECTOR)
        viewer_url = link_tag.get('href') if link_tag and link_tag.get('href') else "N/A"

        if viewer_url != "N/A":
            if viewer_url.startswith('/'): viewer_url = "https://www.hofer.at" + viewer_url
            scraped_data.append({
                "Title": title, "Duration": duration_tag.text.strip() if duration_tag else "N/A", "ViewerURL": viewer_url
            })

    today = date.today()
    parsed_flyers = []
    for flyer in scraped_data:
        sd, ed = parse_hofer_dates(flyer['Duration'], today.year)
        if sd and ed:
            flyer['start_date_obj'] = sd
            flyer['end_date_obj'] = ed
            parsed_flyers.append(flyer)

    valid = [f for f in parsed_flyers if f['end_date_obj'] >= today]
    valid.sort(key=lambda x: x['end_date_obj'], reverse=True) if valid else parsed_flyers.sort(key=lambda x: x['end_date_obj'], reverse=True)
    best = valid[0] if valid else (parsed_flyers[0] if parsed_flyers else None)
        
    if best:
        viewer_url = best.pop("ViewerURL")
        pdf_url = get_pdf_url_via_click(driver, viewer_url, "#downloadAsPdf")
        print(f"HOFER: Found active flyer -> {best['Duration']}")
            
        return [{
            "Title": best["Title"], "Retailer": "HOFER", "PDF_URL": pdf_url if pdf_url else viewer_url,
            "Duration": best["Duration"], "StartDate": best["start_date_obj"].strftime("%Y-%m-%d"), "EndDate": best["end_date_obj"].strftime("%Y-%m-%d")
        }]

    return []


# =========================================================================
# === BILLA SCRAPER LOGIC ===
# =========================================================================

BILLA_URL = "https://www.billa.at/unsere-aktionen/flugblatt"

def scrape_billa(driver):
    print("\n--- Starting BILLA Scraping ---")
    driver.get(BILLA_URL)
    scraped_data = []
    
    try:
        WebDriverWait(driver, WAIT_TIME_SECONDS).until(EC.presence_of_element_located((By.CSS_SELECTOR, 'a[aria-label="BILLA Flugblatt als PDF downloaden"]')))
    except TimeoutException:
        print("BILLA: Timeout waiting for flyer links to appear.")
        return []
    
    today = date.today()
    iso_weekday = today.isoweekday() 
    start_date = today - timedelta(days=(iso_weekday - 4)) if iso_weekday >= 4 else today - timedelta(days=(iso_weekday + 3))
    end_date = start_date + timedelta(days=6)
    duration_text = f"VON DONNERSTAG, {start_date.day:02d}.{start_date.month:02d}. BIS MITTWOCH, {end_date.day:02d}.{end_date.month:02d}.{end_date.year}"
    
    for title, selector in [("BILLA Flugblatt", 'a[aria-label="BILLA Flugblatt als PDF downloaden"]'), 
                            ("BILLA PLUS Flugblatt", 'a[aria-label="BILLA PLUS Flugblatt als PDF downloaden"]')]:
        try:
            pdf_url = driver.find_element(By.CSS_SELECTOR, selector).get_attribute('href')
            scraped_data.append({
                "Title": title, "Retailer": "BILLA", "PDF_URL": pdf_url,
                "Duration": duration_text, "StartDate": start_date.strftime("%Y-%m-%d"), "EndDate": end_date.strftime("%Y-%m-%d")
            })
            print(f"BILLA: Found {title}")
        except NoSuchElementException:
            continue
            
    return scraped_data


# =========================================================================
# === SPAR SCRAPER LOGIC ===
# =========================================================================

SPAR_URLS = [
    "https://www.spar.at/aktionen/wien/spar",
    "https://www.spar.at/aktionen/wien/interspar"
]

def parse_spar_dates(duration_str):
    if not duration_str: return None, None
    matches = re.findall(r'(\d{1,2})\.(\d{1,2})\.(\d{2,4})', duration_str)
    if len(matches) >= 2:
        try:
            sy, ey = int(matches[0][2]), int(matches[-1][2])
            start_date = date(sy if sy >= 100 else sy + 2000, int(matches[0][1]), int(matches[0][0]))
            end_date = date(ey if ey >= 100 else ey + 2000, int(matches[-1][1]), int(matches[-1][0]))
            return start_date, end_date
        except ValueError: pass
    return None, None

def get_base_ipaper_url(article):
    img = article.select_one('img')
    if img:
        for attr in ['src', 'data-fallback-icon']:
            val = img.get(attr, '')
            if '/Image.ashx' in val:
                return val.split('/Image.ashx')[0]
                
    link = article.select_one('a.flyer-teaser__teaser-inner')
    if link and link.get('href'):
        href = link.get('href')
        parts = [p for p in href.split('/') if p]
        if len(parts) >= 3 and parts[0] == 'aktionen':
            path = "/".join(parts[1:])
            domain = "flugblatt.interspar.at" if "interspar" in path else "flugblatt.spar.at"
            return f"https://{domain}/{path}"
    return None

def scrape_spar(driver):
    print("\n--- Starting SPAR Scraping ---")
    scraped_data = []
    
    for url in SPAR_URLS:
        driver.get(url)
        try:
            WebDriverWait(driver, WAIT_TIME_SECONDS).until(EC.presence_of_element_located((By.CSS_SELECTOR, 'article.flyer-teaser__teaser')))
        except TimeoutException:
            continue
            
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        for article in soup.find_all('article', class_='flyer-teaser__teaser'):
            if 'flyer-teaser__teaser--active' not in article.get('class', []): continue
                
            title_tag = article.select_one('.flyer-teaser__caption')
            duration_tag = article.select_one('.flyer-teaser__valid')
            title = title_tag.text.strip() if title_tag else "Title N/A"
            duration = duration_tag.text.strip() if duration_tag else "N/A"
            
            ipaper_url = get_base_ipaper_url(article)
            sd, ed = parse_spar_dates(duration)
            
            scraped_data.append({
                "Title": title,
                "Retailer": article.get('data-type', 'SPAR').strip(),
                "iPaperURL": ipaper_url,
                "Duration": duration,
                "StartDate": sd.strftime("%Y-%m-%d") if sd else "N/A",
                "EndDate": ed.strftime("%Y-%m-%d") if ed else "N/A",
                "start_date_obj": sd, "end_date_obj": ed
            })
                
    today = date.today()
    valid_flyers = [f for f in scraped_data if f.get('end_date_obj') and f['end_date_obj'] >= today]
    main_flyers = [f for f in valid_flyers if 'flugblatt' in f['Title'].lower() and 'sonderfolder' not in f['Title'].lower()]
    if not main_flyers: main_flyers = valid_flyers
            
    final_results = []
    retailers_processed = set()
    main_flyers.sort(key=lambda x: (x['end_date_obj'], x['start_date_obj']), reverse=True)
    
    for flyer in main_flyers:
        ret = flyer['Retailer']
        if ret not in retailers_processed:
            retailers_processed.add(ret)
            print(f"SPAR/INTERSPAR: Selected most relevant for {ret} -> {flyer['Title']}")
            
            ipaper_url = flyer.pop("iPaperURL")
            end_date_str = flyer["EndDate"]
            title_str = flyer["Title"]
            
            # Download the PDF directly in Selenium right now!
            if ipaper_url and end_date_str != "N/A":
                target_filename = f"{ret}_{end_date_str}_{slugify(title_str)}.pdf"
                target_filepath = os.path.join(DOWNLOAD_DIR, target_filename)
                download_spar_pdf_via_selenium(driver, ipaper_url, target_filepath)
            
            # Set PDF_URL to None since it is already downloaded
            flyer["PDF_URL"] = None
            del flyer['start_date_obj']; del flyer['end_date_obj']
            final_results.append(flyer)
            
    return final_results


# =========================================================================
# === PENNY SCRAPER LOGIC ===
# =========================================================================

PENNY_URL = "https://www.penny.at/angebote/flugblaetter"

def parse_penny_dates(text_str, current_year):
    matches = re.findall(r'(\d{1,2})\.(\d{1,2})\.(\d{4})?', text_str)
    if len(matches) >= 2:
        try:
            ey = int(matches[-1][2]) if matches[-1][2] else current_year
            end_date = date(ey, int(matches[-1][1]), int(matches[-1][0]))
            sy = int(matches[0][2]) if matches[0][2] else ey
            start_date = date(sy, int(matches[0][1]), int(matches[0][0]))
            if start_date > end_date: start_date = start_date.replace(year=end_date.year - 1)
            return start_date, end_date
        except ValueError: pass
    return None, None

def scrape_penny(driver):
    print("\n--- Starting PENNY Scraping ---")
    driver.get(PENNY_URL)
    
    try: WebDriverWait(driver, 5).until(EC.element_to_be_clickable((By.ID, "onetrust-accept-btn-handler"))).click()
    except: pass
        
    try: WebDriverWait(driver, WAIT_TIME_SECONDS).until(EC.presence_of_element_located((By.CSS_SELECTOR, 'a.ws-image__wrapper')))
    except TimeoutException: return []
        
    soup = BeautifulSoup(driver.page_source, 'html.parser')
    scraped_data = []
    
    for link in soup.find_all('a', class_='ws-image__wrapper'):
        href = link.get('href', '')
        if 'issuu.com' not in href: continue
            
        aria = link.get('aria-label', '')
        sd, ed = parse_penny_dates(aria if aria else href, date.today().year)
        
        if sd and ed:
            scraped_data.append({
                "Title": "PENNY Flugblatt", "Retailer": "PENNY", 
                "ViewerURL": ("https:" + href) if href.startswith('//') else href, 
                "Duration": aria if aria else "N/A",
                "StartDate": sd.strftime("%Y-%m-%d"), "EndDate": ed.strftime("%Y-%m-%d"),
                "end_date_obj": ed
            })

    valid_flyers = [f for f in scraped_data if f['end_date_obj'] >= date.today()]
    
    if valid_flyers:
        valid_flyers.sort(key=lambda x: x['end_date_obj'], reverse=True)
        best = valid_flyers[0]
        
        viewer_url = best.pop("ViewerURL")
        pdf_url = get_pdf_url_via_click(driver, viewer_url, 'button[aria-label="Download"]')
        
        best["PDF_URL"] = pdf_url if pdf_url else viewer_url
        del best['end_date_obj']
        
        print(f"PENNY: Found active flyer -> {best['Duration']}")
        return [best]
        
    print("PENNY: No active flyers found.")
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
        
        # Ensure Chrome Headless allows downloads
        driver.execute_cdp_cmd("Page.setDownloadBehavior", {
            "behavior": "allow",
            "downloadPath": DOWNLOAD_DIR
        })
        
        hofer_results = scrape_hofer(driver)
        all_flyers.extend(hofer_results)

        billa_results = scrape_billa(driver)
        all_flyers.extend(billa_results)
        
        spar_results = scrape_spar(driver)
        all_flyers.extend(spar_results)
        
        penny_results = scrape_penny(driver)
        all_flyers.extend(penny_results)

    except Exception as e:
        print(f"\nCRITICAL ERROR during script execution: {e}")

    finally:
        if driver: driver.quit()
    
    if all_flyers:
        try:
            with open(OUTPUT_JSON_PATH, 'w', encoding='utf-8') as f:
                json.dump(all_flyers, f, ensure_ascii=False, indent=2)
            print(f"\nSUCCESS: Combined data for {len(all_flyers)} flyers saved to '{OUTPUT_JSON_PATH}'.")
        except Exception as e:
            print(f"ERROR: Could not save JSON file: {e}")
    else:
        print("\nNo relevant PDF links were scraped. Skipping JSON save.")