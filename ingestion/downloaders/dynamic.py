import os
import re
import time
import urllib.parse
from datetime import date, timedelta
import requests
from bs4 import BeautifulSoup

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException

from ingestion.downloaders.base import FlyerDownloader, DOWNLOAD_DIR


def slugify(text):
    text = str(text).lower().strip()
    text = re.sub(r'[^\w\s-]', '', text)
    text = re.sub(r'[-\s]+', '', text)
    return text[:50]


class BaseSeleniumDownloader(FlyerDownloader):
    """Base class that provides a headless Chrome driver and common request helpers."""
    
    def _dest_path(self, week_end: str | None = None, title: str | None = None) -> str:
        # Override to use your new slugified naming convention
        week_end = week_end or self._default_week_end()
        os.makedirs(DOWNLOAD_DIR, exist_ok=True)
        safe_title = slugify(title) if title else "flyer"
        return os.path.join(DOWNLOAD_DIR, f"{self.retailer_code}_{week_end}_{safe_title}.pdf")

    def _get_driver(self):
        options = webdriver.ChromeOptions()
        options.add_argument('--headless=new')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--window-size=1920,1080')
        options.add_argument('user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36')
        options.add_argument('--disable-gpu')
        options.add_argument('--log-level=3')
        
        # Allow PDF direct downloads in headless mode
        chrome_prefs = {
            "download.default_directory": os.path.abspath(DOWNLOAD_DIR),
            "download.prompt_for_download": False,
            "download.directory_upgrade": True,
            "plugins.always_open_pdf_externally": True
        }
        options.add_experimental_option("prefs", chrome_prefs)
        
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=options)
        driver.execute_cdp_cmd("Page.setDownloadBehavior", {
            "behavior": "allow",
            "downloadPath": os.path.abspath(DOWNLOAD_DIR)
        })
        return driver

    def _download_via_requests(self, pdf_url: str, dest_path: str) -> str | None:
        if os.path.exists(dest_path):
            print(f"[{self.retailer_code}] PDF already downloaded for this week.")
            return dest_path
            
        print(f"[{self.retailer_code}] Downloading PDF from {pdf_url}...")
        try:
            response = requests.get(pdf_url, stream=True, timeout=30)
            response.raise_for_status()
            with open(dest_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            return dest_path
        except requests.exceptions.RequestException as e:
            print(f"[{self.retailer_code}] ERROR during download: {e}")
            return None

    def _get_pdf_url_via_click(self, driver, viewer_url, button_selector):
        """Intercepts the JS download behavior to capture the raw PDF URL."""
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
                
            for _ in range(20):
                time.sleep(0.5)
                pdf_url = driver.execute_script("return window.__captured_pdf;")
                if pdf_url:
                    if pdf_url.startswith('/'):
                        parsed = urllib.parse.urlparse(driver.current_url)
                        pdf_url = f"{parsed.scheme}://{parsed.netloc}{pdf_url}"
                    return pdf_url
        except Exception as e:
            print(f"[{self.retailer_code}] Error extracting PDF via JS: {e}")
        return None


# --- RETAILER IMPLEMENTATIONS ---

class BillaDownloader(BaseSeleniumDownloader):
    def __init__(self, retailer_code="billa", title="BILLA Flugblatt"):
        self.retailer_code = retailer_code
        self.title = title
        self.url = "https://www.billa.at/unsere-aktionen/flugblatt"

    def fetch(self) -> str | None:
        driver = self._get_driver()
        try:
            driver.get(self.url)
            selector = f'a[aria-label="{self.title} als PDF downloaden"]'
            
            # Catch the timeout specifically so it doesn't print a huge stacktrace
            try:
                WebDriverWait(driver, 15).until(EC.presence_of_element_located((By.CSS_SELECTOR, selector)))
            except TimeoutException:
                print(f"[{self.retailer_code}] No flyer found for '{self.title}' right now. Skipping gracefully.")
                return None
                
            pdf_url = driver.find_element(By.CSS_SELECTOR, selector).get_attribute('href')
            
            # Date logic
            today = date.today()
            iso_weekday = today.isoweekday() 
            start_date = today - timedelta(days=(iso_weekday - 4)) if iso_weekday >= 4 else today - timedelta(days=(iso_weekday + 3))
            end_date = start_date + timedelta(days=6)
            
            dest = self._dest_path(end_date.strftime("%Y-%m-%d"), self.title)
            return self._download_via_requests(pdf_url, dest)
        except Exception as e:
            print(f"[{self.retailer_code}] Error scraping: {e}")
            return None
        finally:
            driver.quit()


class SparDownloader(BaseSeleniumDownloader):
    def __init__(self, retailer_code, base_url):
        self.retailer_code = retailer_code  # "spar" or "interspar"
        self.base_url = base_url

    def _get_base_ipaper_url(self, article):
        """Matches the exact extraction logic from your working script."""
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

    def fetch(self) -> str | None:
        driver = self._get_driver()
        try:
            driver.get(self.base_url)
            
            try:
                WebDriverWait(driver, 15).until(EC.presence_of_element_located((By.CSS_SELECTOR, 'article.flyer-teaser__teaser')))
            except TimeoutException:
                print(f"[{self.retailer_code}] No flyer teasers found on the page right now. Skipping gracefully.")
                return None
            
            soup = BeautifulSoup(driver.page_source, 'html.parser')
            
            valid_flyers = []
            today = date.today()
            
            # Find and validate flyers exactly like the working script
            for article in soup.find_all('article', class_='flyer-teaser__teaser'):
                if 'flyer-teaser__teaser--active' not in article.get('class', []): 
                    continue
                
                # Ensure it's for the right retailer! (Spar vs Interspar)
                article_retailer = article.get('data-type', '').strip().lower()
                if self.retailer_code == "interspar" and article_retailer != "interspar":
                    continue
                if self.retailer_code == "spar" and article_retailer != "spar":
                    continue
                    
                title_tag = article.select_one('.flyer-teaser__caption')
                title = title_tag.text.strip() if title_tag else "Title NA"
                
                if 'flugblatt' not in title.lower() or 'sonderfolder' in title.lower():
                    continue
                    
                duration_tag = article.select_one('.flyer-teaser__valid')
                duration = duration_tag.text.strip() if duration_tag else ""
                
                # Exact date parsing from the working script
                matches = re.findall(r'(\d{1,2})\.(\d{1,2})\.(\d{2,4})', duration)
                if len(matches) >= 2:
                    sy, ey = int(matches[0][2]), int(matches[-1][2])
                    try:
                        start_date = date(sy if sy >= 100 else sy + 2000, int(matches[0][1]), int(matches[0][0]))
                        end_date = date(ey if ey >= 100 else ey + 2000, int(matches[-1][1]), int(matches[-1][0]))
                        
                        if end_date >= today:
                            valid_flyers.append({
                                "article": article,
                                "title": title,
                                "end_date": end_date,
                                "start_date": start_date
                            })
                    except ValueError:
                        pass

            if not valid_flyers:
                print(f"[{self.retailer_code}] No active main flyer found matching criteria.")
                return None
                
            # Sort by end_date descending, then start_date descending (like original script)
            valid_flyers.sort(key=lambda x: (x['end_date'], x['start_date']), reverse=True)
            best_flyer = valid_flyers[0]
            
            # Extract URL using the robust fallback method
            ipaper_url = self._get_base_ipaper_url(best_flyer["article"])
            if not ipaper_url:
                print(f"[{self.retailer_code}] Could not extract iPaper URL.")
                return None
                
            end_date_str = best_flyer['end_date'].strftime("%Y-%m-%d")
            dest = self._dest_path(end_date_str, best_flyer['title'])
            
            if os.path.exists(dest): 
                print(f"[{self.retailer_code}] PDF already downloaded for this week.")
                return dest
            
            # Let browser handle the download for SPAR
            driver.get(ipaper_url)
            
            try:
                btn = WebDriverWait(driver, 15).until(EC.presence_of_element_located((By.ID, "modDownloadPdfBtn")))
            except TimeoutException:
                print(f"[{self.retailer_code}] Timed out waiting for PDF download button in viewer.")
                return None
                
            files_before = set(os.listdir(DOWNLOAD_DIR))
            
            # Match working script's robust click logic
            try:
                btn.click()
            except:
                driver.execute_script("arguments[0].click();", btn)
                
            print(f"[{self.retailer_code}] Triggered download, waiting for file...")
            
            for _ in range(30):
                time.sleep(0.5)
                new_files = set(os.listdir(DOWNLOAD_DIR)) - files_before
                # Ignoring .crdownload AND .tmp, exactly like your working script!
                completed = [f for f in new_files if f.lower().endswith('.pdf') and not f.lower().endswith('.crdownload') and not f.lower().endswith('.tmp')]
                if completed:
                    src_path = os.path.join(DOWNLOAD_DIR, list(completed)[0])
                    os.rename(src_path, dest)
                    print(f"[{self.retailer_code}] Successfully saved PDF to {dest}")
                    return dest
                    
            print(f"[{self.retailer_code}] Timed out waiting for browser to finish downloading PDF.")
            return None
            
        except Exception as e:
            print(f"[{self.retailer_code}] Error scraping: {e}")
            return None
        finally:
            driver.quit()

class HoferDownloader(BaseSeleniumDownloader):
    def __init__(self, retailer_code="hofer"):
        self.retailer_code = retailer_code
        self.url = "https://www.hofer.at/de/angebote/aktuelle-flugblaetter-und-broschuren.html"

    def fetch(self) -> str | None:
        driver = self._get_driver()
        try:
            driver.get(self.url)
            try:
                WebDriverWait(driver, 5).until(EC.element_to_be_clickable((By.ID, "onetrust-accept-btn-handler"))).click()
            except: pass
            
            WebDriverWait(driver, 15).until(EC.presence_of_element_located((By.CSS_SELECTOR, '.cms-multilayout-teaser')))
            soup = BeautifulSoup(driver.page_source, 'html.parser')
            
            for card in soup.select('.cms-multilayout-teaser'):
                title = card.select_one('.cms-multilayout-teaser__title')
                if title and title.text.strip() == "Flugblatt":
                    duration = card.select_one('.cms-multilayout-teaser__description').text.strip()
                    link = card.select_one('.cms-multilayout-teaser__link')
                    viewer_url = link.get('href') if link else None
                    if viewer_url:
                        if viewer_url.startswith('/'): viewer_url = "https://www.hofer.at" + viewer_url
                        
                        dates = re.findall(r'(\d{1,2})\.(\d{1,2})\.?(\d{4})?', duration)
                        end_date_str = f"{dates[-1][2] or date.today().year}-{dates[-1][1]:0>2}-{dates[-1][0]:0>2}" if dates else self._default_week_end()
                        
                        pdf_url = self._get_pdf_url_via_click(driver, viewer_url, "#downloadAsPdf")
                        if pdf_url:
                            dest = self._dest_path(end_date_str, "Flugblatt")
                            return self._download_via_requests(pdf_url, dest)
            return None
        except Exception as e:
            print(f"[{self.retailer_code}] Error scraping: {e}")
            return None
        finally:
            driver.quit()


class PennyDownloader(BaseSeleniumDownloader):
    def __init__(self, retailer_code="penny"):
        self.retailer_code = retailer_code
        self.url = "https://www.penny.at/angebote/flugblaetter"

    def fetch(self) -> str | None:
        driver = self._get_driver()
        try:
            driver.get(self.url)
            try: WebDriverWait(driver, 5).until(EC.element_to_be_clickable((By.ID, "onetrust-accept-btn-handler"))).click()
            except: pass
            
            WebDriverWait(driver, 15).until(EC.presence_of_element_located((By.CSS_SELECTOR, 'a.ws-image__wrapper')))
            soup = BeautifulSoup(driver.page_source, 'html.parser')
            
            for link in soup.find_all('a', class_='ws-image__wrapper'):
                href = link.get('href', '')
                if 'issuu.com' in href:
                    viewer_url = ("https:" + href) if href.startswith('//') else href
                    aria = link.get('aria-label', '')
                    dates = re.findall(r'(\d{1,2})\.(\d{1,2})\.(\d{4})?', aria if aria else href)
                    end_date_str = f"{dates[-1][2] or date.today().year}-{dates[-1][1]:0>2}-{dates[-1][0]:0>2}" if dates else self._default_week_end()
                    
                    pdf_url = self._get_pdf_url_via_click(driver, viewer_url, 'button[aria-label="Download"]')
                    if pdf_url:
                        dest = self._dest_path(end_date_str, "PENNY Flugblatt")
                        return self._download_via_requests(pdf_url, dest)
            return None
        except Exception as e:
            print(f"[{self.retailer_code}] Error scraping: {e}")
            return None
        finally:
            driver.quit()
            
class LidlDownloader(BaseSeleniumDownloader):
    def __init__(self, retailer_code="lidl"):
        self.retailer_code = retailer_code
        self.url = "https://www.lidl.at/c/flugblatt/s10012330"

    def fetch(self) -> str | None:
        driver = self._get_driver()
        try:
            driver.get(self.url)
            
            try:
                WebDriverWait(driver, 15).until(EC.presence_of_element_located((By.CSS_SELECTOR, 'a.flyer')))
            except TimeoutException:
                print(f"[{self.retailer_code}] No flyers found on the page right now. Skipping.")
                return None
            
            soup = BeautifulSoup(driver.page_source, 'html.parser')
            
            # 1. Find the first flyer link
            for flyer_link in soup.find_all('a', class_='flyer'):
                href = flyer_link.get('href', '')
                
                # 2. Extract the identifier (e.g. "ab-donnerstag-6-8-flugblatt-grd")
                match = re.search(r'/flugblatt/([^/]+)/', href)
                if not match:
                    continue
                    
                identifier = match.group(1)
                
                # 3. Hit the hidden JSON API directly!
                api_url = f"https://endpoints.leaflets.schwarz/v4/flyer?flyer_identifier={identifier}&region_id=1"
                print(f"[{self.retailer_code}] Querying hidden API: {api_url}")
                
                api_resp = requests.get(api_url, timeout=15)
                if api_resp.status_code == 200:
                    data = api_resp.json()
                    flyer_data = data.get("flyer", {})
                    
                    pdf_url = flyer_data.get("pdfUrl")
                    end_date_str = flyer_data.get("endDate")  # e.g., "2026-08-12"
                    title = flyer_data.get("name", "Flugblatt")
                    
                    if not pdf_url or not end_date_str:
                        continue
                        
                    # 4. Check if flyer is still active
                    try:
                        ed = date.fromisoformat(end_date_str)
                        if ed < date.today():
                            continue # Flyer is expired
                    except ValueError:
                        pass
                    
                    # 5. Download it using the direct URL!
                    dest = self._dest_path(end_date_str, title)
                    if os.path.exists(dest): 
                        print(f"[{self.retailer_code}] PDF already downloaded for this week.")
                        return dest
                        
                    return self._download_via_requests(pdf_url, dest)
                    
            print(f"[{self.retailer_code}] No active PDF links could be extracted.")
            return None
            
        except Exception as e:
            print(f"[{self.retailer_code}] Error scraping: {e}")
            return None
        finally:
            driver.quit()