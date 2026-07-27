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


# =========================================================================
# === ADVANCED JS INTERCEPTOR (For dynamic PDF downloads) ===
# =========================================================================

def get_pdf_url_via_click(driver, viewer_url, button_selector):
    """
    Navigates to the viewer URL, handles iframes, injects a JS script to intercept 
    programmatic download behavior, clicks the download button, and captures the raw PDF URL.
    """
    print(f"   -> Navigating to viewer: {viewer_url}")
    driver.get(viewer_url)
    time.sleep(3) # Give viewer time to build its DOM
    
    # Clear any annoying cookie banners if present in main context
    try:
        driver.find_element(By.ID, "onetrust-accept-btn-handler").click()
        time.sleep(1)
    except:
        pass

    # --- IFRAME HANDLING ---
    # Many viewers (Spar/iPaper) are embedded in iframes.
    iframes = driver.find_elements(By.TAG_NAME, "iframe")
    switched_to_iframe = False
    for iframe in iframes:
        src = iframe.get_attribute("src") or ""
        if "flugblatt" in src or "ipaper" in src or "issuu" in src or "katalog" in src:
            driver.switch_to.frame(iframe)
            print("   -> Switched to viewer iframe.")
            switched_to_iframe = True
            time.sleep(1)
            break
            
    # Inject JS interceptors into the active context to catch the URL request
    driver.execute_script("""
        window.__captured_pdf = null;
        
        // 1. Intercept window.open
        window.open = function(url, name, specs) {
            window.__captured_pdf = url;
            return null;
        };
        
        // 2. Intercept programmatic anchor clicks
        var origClick = HTMLAnchorElement.prototype.click;
        HTMLAnchorElement.prototype.click = function() {
            if (this.href) { window.__captured_pdf = this.href; }
        };
        
        // 3. Intercept redirect assignments
        window.location.assign = function(url) { window.__captured_pdf = url; };
        window.location.replace = function(url) { window.__captured_pdf = url; };
        
        // 4. Intercept hidden iframes (often used for seamless downloading)
        var origAppend = Element.prototype.appendChild;
        Element.prototype.appendChild = function(child) {
            if (child.tagName === 'IFRAME' && child.src) {
                window.__captured_pdf = child.src;
            }
            return origAppend.apply(this, arguments);
        };
        
        // 5. Catch-all listener for strict DOM link clicks
        document.addEventListener('click', function(e) {
            var el = e.target.closest ? e.target.closest('a') : null;
            if (el && el.href && (el.hasAttribute('download') || el.target === '_blank' || el.href.includes('.pdf'))) {
                window.__captured_pdf = el.href;
                e.preventDefault();
            }
        }, true);
    """)
    
    try:
        # Wait for the download button to exist
        btn = WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.CSS_SELECTOR, button_selector)))
        
        # Click the button (fallback to JS click if hidden by an overlay)
        try:
            btn.click()
        except:
            driver.execute_script("arguments[0].click();", btn)
            
        print("   -> Download triggered. Intercepting URL request...")
        
        # Poll up to 10 seconds for the URL to be caught by our JS hooks
        for _ in range(20):
            time.sleep(0.5)
            pdf_url = driver.execute_script("return window.__captured_pdf;")
            
            if pdf_url:
                if pdf_url.startswith('/'):
                    parsed = urllib.parse.urlparse(driver.current_url)
                    pdf_url = f"{parsed.scheme}://{parsed.netloc}{pdf_url}"
                print("   -> Success! Direct PDF URL intercepted via JS.")
                if switched_to_iframe: driver.switch_to.default_content()
                return pdf_url
                
            # If the iframe/page itself navigated directly to the PDF
            if ".pdf" in driver.current_url.lower() and "viewer" not in driver.current_url.lower() and "embed" not in driver.current_url.lower():
                print("   -> Success! Intercepted via current_url change.")
                url_to_return = driver.current_url
                if switched_to_iframe: driver.switch_to.default_content()
                return url_to_return
                
    except TimeoutException:
        print(f"   -> Timeout waiting for download button: {button_selector}")
    except Exception as e:
        print(f"   -> Error extracting PDF via JS: {e}")
        
    if switched_to_iframe: driver.switch_to.default_content()
    return None


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
    html_content = driver.page_source
    soup = BeautifulSoup(html_content, 'html.parser')
    flyer_cards = soup.select(HOFER_FLYER_CARD_SELECTOR)
    
    for card in flyer_cards:
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
            link_tag = article.select_one('a.flyer-teaser__teaser-inner')
            href = link_tag.get('href') if link_tag else None
            
            if href:
                img_tag = article.select_one('img.flyer-teaser__image')
                
                # Retrieve the raw iPaper base URL directly to bypass the www.spar.at wrapper frame 
                if img_tag and img_tag.get('src') and '/Image.ashx' in img_tag.get('src'):
                    base_ipaper_url = img_tag.get('src').split('/Image.ashx')[0]
                    viewer_url = base_ipaper_url
                else:
                    viewer_url = f"https://www.spar.at{href}" if href.startswith('/') else href
                    
                duration = duration_tag.text.strip() if duration_tag else "N/A"
                sd, ed = parse_spar_dates(duration)
                scraped_data.append({
                    "Title": title_tag.text.strip() if title_tag else "Title N/A",
                    "Retailer": article.get('data-type', 'SPAR').strip(),
                    "ViewerURL": viewer_url,
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
            
            viewer_url = flyer.pop("ViewerURL")
            pdf_url = get_pdf_url_via_click(driver, viewer_url, "#modDownloadPdfBtn")
            
            flyer["PDF_URL"] = pdf_url if pdf_url else viewer_url
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