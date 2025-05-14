import time
import os
import re
import pandas as pd
import sqlite3
from datetime import datetime
from playwright.sync_api import sync_playwright
from tqdm import tqdm
import threading
import requests
from urllib.parse import urlparse
from pathlib import Path


class Database:
    """SQLite database manager for storing scraping results"""
    
    def __init__(self, db_path="iboss_data/iboss_scraper.db"):
        """Initialize the database connection"""
        # Ensure directory exists
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.lock = threading.Lock()  # Lock for thread safety
        self.cursor = self.conn.cursor()
        self._create_tables()
    
    def _create_tables(self):
        """Create tables for storing scraping data"""
        with self.lock:
            # Categories table
            self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS categories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                category_name TEXT NOT NULL,
                category_link TEXT NOT NULL,
                agency_count INTEGER,
                scraped BOOLEAN DEFAULT 0,
                last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            ''')
            
            # Agencies table
            self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS agencies (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                category_id INTEGER,
                category_name TEXT NOT NULL,
                agency_name TEXT NOT NULL,
                agency_url TEXT,
                agency_logo TEXT,
                local_logo_path TEXT,
                agency_desc TEXT,
                agency_idx TEXT,
                agency_detail_url TEXT,
                agency_detail_desc TEXT,
                detailed_scraped BOOLEAN DEFAULT 0,
                last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (category_id) REFERENCES categories (id)
            )
            ''')
            
            # Scraping_status table for tracking progress
            self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS scraping_status (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_start TIMESTAMP,
                session_end TIMESTAMP,
                categories_total INTEGER DEFAULT 0,
                categories_scraped INTEGER DEFAULT 0,
                agencies_total INTEGER DEFAULT 0,
                agencies_scraped INTEGER DEFAULT 0,
                details_total INTEGER DEFAULT 0,
                details_scraped INTEGER DEFAULT 0,
                status TEXT
            )
            ''')
            
            self.conn.commit()
    
    def insert_category(self, category_name, category_link, agency_count):
        """Insert a category into the database"""
        with self.lock:
            # Check if category already exists
            self.cursor.execute(
                "SELECT id FROM categories WHERE category_name = ?", 
                (category_name,)
            )
            existing = self.cursor.fetchone()
            
            if existing:
                # Update existing category
                self.cursor.execute(
                    "UPDATE categories SET category_link = ?, agency_count = ?, last_updated = CURRENT_TIMESTAMP WHERE id = ?",
                    (category_link, agency_count, existing[0])
                )
                category_id = existing[0]
            else:
                # Insert new category
                self.cursor.execute(
                    "INSERT INTO categories (category_name, category_link, agency_count, last_updated) VALUES (?, ?, ?, CURRENT_TIMESTAMP)",
                    (category_name, category_link, agency_count)
                )
                category_id = self.cursor.lastrowid
            
            self.conn.commit()
            return category_id
    
    def insert_agency(self, category_id, category_name, agency_name, agency_url, agency_logo, agency_desc, agency_idx=None, agency_detail_url=None, local_logo_path=None):
        """Insert an agency into the database"""
        with self.lock:
            # Check if agency already exists for this category
            self.cursor.execute(
                "SELECT id FROM agencies WHERE category_id = ? AND agency_name = ?", 
                (category_id, agency_name)
            )
            existing = self.cursor.fetchone()
            
            if existing:
                # Update existing agency
                self.cursor.execute(
                    "UPDATE agencies SET agency_url = ?, agency_logo = ?, local_logo_path = ?, agency_desc = ?, agency_idx = ?, agency_detail_url = ?, last_updated = CURRENT_TIMESTAMP WHERE id = ?",
                    (agency_url, agency_logo, local_logo_path, agency_desc, agency_idx, agency_detail_url, existing[0])
                )
                agency_id = existing[0]
            else:
                # Insert new agency
                self.cursor.execute(
                    "INSERT INTO agencies (category_id, category_name, agency_name, agency_url, agency_logo, local_logo_path, agency_desc, agency_idx, agency_detail_url, last_updated) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)",
                    (category_id, category_name, agency_name, agency_url, agency_logo, local_logo_path, agency_desc, agency_idx, agency_detail_url)
                )
                agency_id = self.cursor.lastrowid
            
            self.conn.commit()
            return agency_id
    
    def update_agency_detail(self, agency_id, detail_desc):
        """Update agency with detailed description"""
        with self.lock:
            self.cursor.execute(
                "UPDATE agencies SET agency_detail_desc = ?, detailed_scraped = 1, last_updated = CURRENT_TIMESTAMP WHERE id = ?",
                (detail_desc, agency_id)
            )
            self.conn.commit()
    
    def get_agency_by_id(self, agency_id):
        """Get agency by its ID"""
        with self.lock:
            self.cursor.execute(
                "SELECT id, agency_name, agency_idx, agency_detail_url FROM agencies WHERE id = ?",
                (agency_id,)
            )
            return self.cursor.fetchone()
    
    def get_agencies_without_details(self):
        """Get agencies that don't have detailed descriptions yet"""
        with self.lock:
            self.cursor.execute(
                "SELECT id, agency_name, agency_idx, agency_detail_url FROM agencies WHERE detailed_scraped = 0"
            )
            return self.cursor.fetchall()
    
    def mark_category_scraped(self, category_id):
        """Mark a category as scraped"""
        with self.lock:
            self.cursor.execute(
                "UPDATE categories SET scraped = 1, last_updated = CURRENT_TIMESTAMP WHERE id = ?",
                (category_id,)
            )
            self.conn.commit()
    
    def get_unscraped_categories(self):
        """Get all categories that haven't been scraped yet"""
        with self.lock:
            self.cursor.execute(
                "SELECT id, category_name, category_link, agency_count FROM categories WHERE scraped = 0"
            )
            return self.cursor.fetchall()
    
    def get_categories(self):
        """Get all categories"""
        with self.lock:
            self.cursor.execute(
                "SELECT id, category_name, category_link, agency_count, scraped FROM categories"
            )
            return self.cursor.fetchall()
    
    def get_agencies_by_category(self, category_id):
        """Get all agencies for a specific category"""
        with self.lock:
            self.cursor.execute(
                "SELECT agency_name, agency_url, agency_logo, agency_desc, agency_detail_desc FROM agencies WHERE category_id = ?",
                (category_id,)
            )
            return self.cursor.fetchall()
    
    def get_all_agencies(self):
        """Get all agencies"""
        with self.lock:
            self.cursor.execute(
                "SELECT category_name, agency_name, agency_url, agency_logo, agency_desc, agency_detail_desc FROM agencies"
            )
            return self.cursor.fetchall()
    
    def count_agencies(self):
        """Count total number of agencies"""
        with self.lock:
            self.cursor.execute("SELECT COUNT(*) FROM agencies")
            return self.cursor.fetchone()[0]
    
    def count_agencies_with_details(self):
        """Count agencies with detailed descriptions"""
        with self.lock:
            self.cursor.execute("SELECT COUNT(*) FROM agencies WHERE detailed_scraped = 1")
            return self.cursor.fetchone()[0]
    
    def start_scraping_session(self):
        """Record the start of a scraping session"""
        with self.lock:
            self.cursor.execute(
                "INSERT INTO scraping_status (session_start, status) VALUES (CURRENT_TIMESTAMP, 'running')"
            )
            self.conn.commit()
            return self.cursor.lastrowid
    
    def update_scraping_status(self, session_id, categories_total=None, categories_scraped=None, 
                              agencies_total=None, agencies_scraped=None, details_total=None, 
                              details_scraped=None, status=None):
        """Update the status of a scraping session"""
        with self.lock:
            update_fields = []
            values = []
            
            if categories_total is not None:
                update_fields.append("categories_total = ?")
                values.append(categories_total)
            
            if categories_scraped is not None:
                update_fields.append("categories_scraped = ?")
                values.append(categories_scraped)
            
            if agencies_total is not None:
                update_fields.append("agencies_total = ?")
                values.append(agencies_total)
            
            if agencies_scraped is not None:
                update_fields.append("agencies_scraped = ?")
                values.append(agencies_scraped)
            
            if details_total is not None:
                update_fields.append("details_total = ?")
                values.append(details_total)
            
            if details_scraped is not None:
                update_fields.append("details_scraped = ?")
                values.append(details_scraped)
            
            if status is not None:
                update_fields.append("status = ?")
                values.append(status)
            
            if status == 'completed':
                update_fields.append("session_end = CURRENT_TIMESTAMP")
            
            if update_fields:
                query = f"UPDATE scraping_status SET {', '.join(update_fields)} WHERE id = ?"
                values.append(session_id)
                
                self.cursor.execute(query, values)
                self.conn.commit()
    
    def export_to_csv(self, export_dir="iboss_data"):
        """Export database contents to CSV files"""
        print(f"Exporting database to CSV files in {export_dir}")
        
        # Ensure directory exists
        os.makedirs(export_dir, exist_ok=True)
        
        with self.lock:
            try:
                # Export categories
                self.cursor.execute("SELECT * FROM categories")
                categories = self.cursor.fetchall()
                
                if categories:
                    df_categories = pd.DataFrame(categories, columns=[
                        'id', 'category_name', 'category_link', 'agency_count', 'scraped', 'last_updated'
                    ])
                    category_path = os.path.join(export_dir, 'categories.csv')
                    df_categories.to_csv(category_path, index=False, encoding='utf-8-sig')
                    print(f"Exported {len(categories)} categories to {category_path}")
                
                # Export agencies
                self.cursor.execute("SELECT * FROM agencies")
                agencies = self.cursor.fetchall()
                
                if agencies:
                    df_agencies = pd.DataFrame(agencies, columns=[
                        'id', 'category_id', 'category_name', 'agency_name', 'agency_url', 
                        'agency_logo', 'local_logo_path', 'agency_desc', 'agency_idx', 'agency_detail_url', 
                        'agency_detail_desc', 'detailed_scraped', 'last_updated'
                    ])
                    agency_path = os.path.join(export_dir, 'agencies.csv')
                    df_agencies.to_csv(agency_path, index=False, encoding='utf-8-sig')
                    print(f"Exported {len(agencies)} agencies to {agency_path}")
                
                # Export scraping status
                self.cursor.execute("SELECT * FROM scraping_status")
                status = self.cursor.fetchall()
                
                if status:
                    df_status = pd.DataFrame(status, columns=[
                        'id', 'session_start', 'session_end', 'categories_total', 
                        'categories_scraped', 'agencies_total', 'agencies_scraped',
                        'details_total', 'details_scraped', 'status'
                    ])
                    status_path = os.path.join(export_dir, 'scraping_status.csv')
                    df_status.to_csv(status_path, index=False, encoding='utf-8-sig')
                    print(f"Exported scraping status to {status_path}")
                
                return True
            
            except Exception as e:
                print(f"Error exporting to CSV: {e}")
                return False
    
    def close(self):
        """Close the database connection"""
        if hasattr(self, 'conn') and self.conn:
            self.conn.close()


class IBossScraper:
    def __init__(self, headless=False, db_path="iboss_data/iboss_scraper.db", target_categories=None, max_agencies_per_category=0, skip_details=False, output_dir="iboss_data"):
        self.playwright = sync_playwright().start()
        self.browser = self.playwright.chromium.launch(headless=headless)
        self.context = self.browser.new_context(viewport={"width": 1920, "height": 1080})
        self.page = self.context.new_page()
        
        # Set default timeout
        self.page.set_default_timeout(30000)
        
        self.base_url = "https://www.i-boss.co.kr"
        
        # Create directory for data if it doesn't exist
        self.data_dir = output_dir
        os.makedirs(self.data_dir, exist_ok=True)
        
        # Create logos directory
        self.logos_dir = os.path.join(self.data_dir, "logos")
        os.makedirs(self.logos_dir, exist_ok=True)
        
        # Initialize database
        self.db = Database(db_path)
        
        # Initialize scraping session
        self.session_id = self.db.start_scraping_session()
        
        # Track statistics
        self.categories_total = 0
        self.categories_scraped = 0
        self.agencies_total = 0
        self.agencies_scraped = 0
        self.details_total = 0
        self.details_scraped = 0
        
        # Filter categories to scrape if specified
        self.target_categories = target_categories
        
        # Limit number of agencies per category if specified
        self.max_agencies_per_category = max_agencies_per_category
        
        # Skip detailed descriptions if specified
        self.skip_details = skip_details
    
    def navigate_to_url(self, url, retries=3):
        """Navigate to a URL and handle loading"""
        for attempt in range(retries):
            try:
                # Check if URL is absolute, if not make it absolute
                if not url.startswith(('http://', 'https://')):
                    url = f"{self.base_url}{url}"
                    
                print(f"Navigating to: {url}")
                self.page.goto(url, wait_until="domcontentloaded")
                self.page.wait_for_load_state("networkidle")
                time.sleep(2)  # Additional wait for content to load
                return True
            except Exception as e:
                print(f"Error navigating to {url} (attempt {attempt+1}/{retries}): {e}")
                if attempt == retries - 1:
                    return False
                time.sleep(2)  # Wait before retry
    
    def get_categories(self):
        """Get all agency categories from the main page"""
        print("Extracting agency categories...")
        
        try:
            # Navigate to the main directory page
            self.navigate_to_url(f"{self.base_url}/ab-7553")
            
            # Wait for the categories to load
            self.page.wait_for_selector("#_LF_agency_dir > div.bg_fff.fix_1050 > div:nth-child(1) > div.category_wrap > ul > li > a")
            
            # Find all category elements
            category_elements = self.page.query_selector_all("#_LF_agency_dir > div.bg_fff.fix_1050 > div:nth-child(1) > div.category_wrap > ul > li > a")
            
            self.categories_total = len(category_elements)
            self.db.update_scraping_status(self.session_id, categories_total=self.categories_total)
            
            categories_data = []
            for element in tqdm(category_elements):
                try:
                    element_text = element.inner_text()
                    text_parts = element_text.split('\n')
                    
                    category_name = text_parts[0] if text_parts else ""
                    agency_count = text_parts[1].replace('개의 대행사', '').strip() if len(text_parts) > 1 else "0"
                    category_link = element.get_attribute('href')
                    
                    # Make sure we have absolute URLs
                    if not category_link.startswith(('http://', 'https://')):
                        category_link = f"{self.base_url}{category_link}"
                    
                    # Store in database
                    category_id = self.db.insert_category(category_name, category_link, agency_count)
                    
                    categories_data.append({
                        'id': category_id,
                        'category_name': category_name,
                        'category_link': category_link,
                        'agency_count': agency_count
                    })
                except Exception as e:
                    print(f"Error extracting category data: {e}")
            
            print(f"Extracted {len(categories_data)} categories")
            return categories_data
        
        except Exception as e:
            print(f"Error getting categories: {e}")
            return []
    
    def extract_agency_idx(self, href):
        """Extract agency index from the href attribute"""
        try:
            if not href:
                return None
            
            # Use regex to find idx parameter
            match = re.search(r'idx=(\d+)', href)
            if match:
                return match.group(1)
            return None
        except Exception as e:
            print(f"Error extracting agency idx: {e}")
            return None
    
    def download_logo(self, logo_url, category_name, agency_name):
        """Download agency logo and save it as [category_name].png"""
        if not logo_url or logo_url == "N/A":
            print(f"No logo URL available for {agency_name}")
            return None
            
        try:
            # Sanitize filename (remove invalid characters)
            sanitized_category = re.sub(r'[\\/*?:"<>|]', "_", category_name)
            sanitized_agency = re.sub(r'[\\/*?:"<>|]', "_", agency_name)
            
            # Create logo filename
            logo_filename = f"{sanitized_category}_{sanitized_agency}.png"
            logo_path = os.path.join(self.logos_dir, logo_filename)
            
            # Check if file already exists
            if os.path.exists(logo_path):
                print(f"Logo for {agency_name} already exists at {logo_path}")
                return logo_path
                
            print(f"Downloading logo for {agency_name} from {logo_url}")
            
            # Download the image
            response = requests.get(logo_url, stream=True, timeout=10)
            if response.status_code == 200:
                with open(logo_path, 'wb') as f:
                    for chunk in response.iter_content(1024):
                        f.write(chunk)
                print(f"Logo saved to {logo_path}")
                return logo_path
            else:
                print(f"Failed to download logo: HTTP status {response.status_code}")
                return None
                
        except Exception as e:
            print(f"Error downloading logo for {agency_name}: {e}")
            return None
    
    def get_agencies_in_category(self, category_id, category_name, category_url):
        """Get all agencies within a specific category"""
        print(f"\nExtracting agencies for category: {category_name}")
        agencies_data = []
        agencies_collected = 0
        
        try:
            # Navigate to category page
            self.navigate_to_url(category_url)
            
            # Look for the agency list selector
            try:
                print("Waiting for agency list selector...")
                self.page.wait_for_selector("div._list > div", timeout=10000)
                print("Agency list selector found.")
            except Exception as e:
                print(f"Warning: Agency list not found immediately, trying alternate approach: {e}")
                # Try an alternative approach - sometimes div._list might be loaded dynamically
                time.sleep(5)
                
            # Initialize pagination parameters
            current_page = 1
            has_next_page = True
            
            # Process all pages
            while has_next_page:
                print(f"Processing page {current_page}...")
                
                # Wait a bit for content to load
                time.sleep(2)
                
                # Find all agency listings on current page
                agency_elements = self.page.query_selector_all("div._list > div")
                
                if not agency_elements:
                    print("No agency elements found on this page. Checking if we need a different selector...")
                    # Sometimes the structure might be different
                    alternate_elements = self.page.query_selector_all("div.conts div[class^='list_'] > div")
                    if alternate_elements:
                        print(f"Found {len(alternate_elements)} agencies using alternate selector")
                        agency_elements = alternate_elements
                
                print(f"Found {len(agency_elements)} agency elements")
                
                # Debug: Print the HTML structure of the first element if available
                if agency_elements and len(agency_elements) > 0:
                    print("First element HTML structure:")
                    print(agency_elements[0].inner_html()[:200] + "..." if len(agency_elements[0].inner_html()) > 200 else agency_elements[0].inner_html())
                
                for idx, agency in enumerate(agency_elements):
                    try:
                        # Check if we've reached the maximum number of agencies to collect
                        if self.max_agencies_per_category > 0 and agencies_collected >= self.max_agencies_per_category:
                            print(f"Reached maximum number of agencies ({self.max_agencies_per_category}) for category {category_name}")
                            has_next_page = False
                            break
                        
                        print(f"Processing agency {idx+1}/{len(agency_elements)}...")
                        
                        # Get agency elements
                        agency_html = agency.inner_html()
                        print(f"Agency HTML: {agency_html[:100]}..." if len(agency_html) > 100 else agency_html)
                        
                        # Extract data from each agency listing
                        agency_name_elem = agency.query_selector("a.link_tit > span.AB-LF-common") or agency.query_selector("a > span[class*='AB-']")
                        
                        if not agency_name_elem:
                            print(f"No agency name element found for agency {idx+1}. Trying alternative selectors...")
                            agency_name_elem = agency.query_selector("a[class*='link_'] > span") or agency.query_selector("a > span")
                        
                        if not agency_name_elem:
                            print(f"Still could not find agency name for agency {idx+1}. Skipping this agency.")
                            continue
                            
                        agency_name = agency_name_elem.inner_text() if agency_name_elem else "N/A"
                        print(f"Agency name: {agency_name}")
                        
                        # Get agency idx from the link
                        link_elem = None
                        href = None
                        if agency_name_elem:
                            try:
                                # Try to directly find the closest anchor tag
                                link_elem = agency.query_selector("a.link_tit") or agency.query_selector("a[href*='idx=']")
                                print(f"Direct link element search: {link_elem}")
                                
                                if not link_elem:
                                    # Try the JS evaluate approach to find the closest parent anchor
                                    try:
                                        link_js = agency_name_elem.evaluate("""
                                            node => {
                                                const closest = node.closest('a');
                                                return closest ? closest.getAttribute('href') : null;
                                            }
                                        """)
                                        if link_js:
                                            href = link_js
                                            print(f"Link href from JS evaluation: {href}")
                                    except Exception as e:
                                        print(f"Error in JS evaluation: {e}")
                                else:
                                    # Get href from the direct link element
                                    href = link_elem.get_attribute('href')
                                    print(f"Link href from direct element: {href}")
                            except Exception as e:
                                print(f"Error finding link element: {e}")
                        
                        agency_idx = None
                        agency_detail_url = None
                        
                        if href:
                            try:
                                agency_idx = self.extract_agency_idx(href)
                                if agency_idx:
                                    agency_detail_url = f"{self.base_url}/ab-7554-{agency_idx}"
                                    print(f"Agency detail URL: {agency_detail_url}")
                            except Exception as e:
                                print(f"Error extracting agency_idx: {e}")
                        
                        # Get URL element - may be different structure
                        agency_url_elem = agency.query_selector("div.url > a.link_tit") or agency.query_selector("div.url > a")
                        if not agency_url_elem:
                            print(f"No URL element found for agency {idx+1}. Trying alternative selectors...")
                            agency_url_elem = agency.query_selector("div[class*='url'] > a") or agency.query_selector("a[class*='link_url']")
                        
                        agency_url = agency_url_elem.inner_text() if agency_url_elem else "N/A"
                        print(f"Agency URL: {agency_url}")
                        
                        # Get logo URL
                        logo_elem = agency.query_selector("div.logo_thumb > a > img") or agency.query_selector("div[class*='logo'] > a > img")
                        if not logo_elem:
                            print(f"No logo element found for agency {idx+1}. Trying alternative selectors...")
                            logo_elem = agency.query_selector("div[class*='logo'] img") or agency.query_selector("img[class*='logo']") or agency.query_selector("img")
                        
                        logo_url = None
                        if logo_elem:
                            try:
                                logo_url = logo_elem.get_attribute('src')
                                print(f"Logo URL: {logo_url}")
                            except Exception as e:
                                print(f"Error getting logo src: {e}")
                                logo_url = "N/A"
                        else:
                            logo_url = "N/A"
                            
                        # Download the logo
                        local_logo_path = None
                        if logo_url and logo_url != "N/A":
                            local_logo_path = self.download_logo(logo_url, category_name, agency_name)
                        
                        # Get description
                        desc_elem = agency.query_selector("p.desc") or agency.query_selector("p[class*='desc']")
                        if not desc_elem:
                            print(f"No description element found for agency {idx+1}. Trying alternative selectors...")
                            desc_elem = agency.query_selector("p") or agency.query_selector("div[class*='desc']")
                        
                        description = desc_elem.inner_text() if desc_elem else "N/A"
                        print(f"Description: {description[:50]}..." if len(description) > 50 else description)
                        
                        # Store in database
                        agency_id = self.db.insert_agency(
                            category_id,
                            category_name,
                            agency_name,
                            agency_url,
                            logo_url,
                            description,
                            agency_idx,
                            agency_detail_url,
                            local_logo_path
                        )
                        
                        self.agencies_scraped += 1
                        agencies_collected += 1
                        self.db.update_scraping_status(
                            self.session_id, 
                            agencies_scraped=self.agencies_scraped
                        )
                        
                        agencies_data.append({
                            'id': agency_id,
                            'agency_name': agency_name,
                            'agency_url': agency_url,
                            'agency_logo': logo_url,
                            'local_logo_path': local_logo_path,
                            'agency_desc': description,
                            'agency_idx': agency_idx,
                            'agency_detail_url': agency_detail_url
                        })
                        
                        print(f"Successfully processed agency: {agency_name}")
                        
                    except Exception as e:
                        print(f"Error extracting agency data for agency {idx+1}: {e}")
                        import traceback
                        traceback.print_exc()
                
                # Check if we've reached the maximum number of agencies to collect
                if self.max_agencies_per_category > 0 and agencies_collected >= self.max_agencies_per_category:
                    print(f"Reached maximum number of agencies ({self.max_agencies_per_category}) for category {category_name}")
                    has_next_page = False
                    break
                
                # Try to find and click the next page button if available
                try:
                    # First look for pagination controls - try multiple selectors
                    pagination_selectors = [
                        "div.paging", 
                        "div[class*='paging']",
                        "ul.pagination",
                        "div.pagination",
                        "nav.pagination",
                        ".page_nav",
                        "[class*='pagination']",
                        "[class*='page_navi']",
                        "div.bbsPaging"
                    ]
                    
                    pagination = None
                    for selector in pagination_selectors:
                        try:
                            pagination = self.page.query_selector(selector)
                            if pagination:
                                print(f"Found pagination with selector: {selector}")
                                break
                        except Exception:
                            continue
                    
                    if not pagination:
                        print("No pagination controls found, assuming this is the only page")
                        # Take a screenshot for debugging
                        screenshot_path = f"{self.data_dir}/pagination_debug_{category_name}_{current_page}.png"
                        self.page.screenshot(path=screenshot_path)
                        print(f"Screenshot saved to {screenshot_path}")
                        has_next_page = False
                        continue
                    
                    # Output the HTML of the pagination element for debugging
                    pagination_html = pagination.inner_html()
                    print(f"Pagination HTML: {pagination_html[:200]}..." if len(pagination_html) > 200 else pagination_html)
                    
                    # Find all links within pagination
                    page_links = pagination.query_selector_all("a") or pagination.query_selector_all("button") or pagination.query_selector_all("span[onclick]")
                    
                    if not page_links:
                        print("No pagination links found, assuming this is the only page")
                        has_next_page = False
                        continue
                    
                    print(f"Found {len(page_links)} pagination links")
                    
                    # Look for a "Next" button - try various text patterns
                    next_button = None
                    next_text_patterns = ['다음', '>', 'next', '→', '▶', 'Next Page', '다음 페이지']
                    
                    for elem in page_links:
                        elem_text = elem.inner_text().strip()
                        elem_html = elem.inner_html()
                        print(f"Pagination element: text='{elem_text}', html='{elem_html[:50]}...'")
                        
                        # Check text content
                        if any(pattern in elem_text or pattern == elem_text for pattern in next_text_patterns):
                            next_button = elem
                            print(f"Found next button with text: {elem_text}")
                            break
                        
                        # Check for SVG or image-based next buttons
                        if "next" in elem_html.lower() or "arr" in elem_html.lower() or "right" in elem_html.lower():
                            next_button = elem
                            print(f"Found next button with HTML containing next/arrow indicators")
                            break
                        
                        # Check aria-label
                        aria_label = elem.get_attribute('aria-label') or ''
                        if any(pattern in aria_label.lower() for pattern in ['next', '다음']):
                            next_button = elem
                            print(f"Found next button with aria-label: {aria_label}")
                            break
                    
                    # If still not found, try to find by position (last item or after current page)
                    if not next_button and len(page_links) > 1:
                        # Try to identify current page using known class names
                        current_page_elem = None
                        for elem in page_links:
                            class_attr = elem.get_attribute('class') or ''
                            # 추가: LF_page_link_current 클래스 확인
                            if ('LF_page_link_current' in class_attr) or ('active' in class_attr) or ('current' in class_attr):
                                current_page_elem = elem
                                print(f"Found current page element with class: {class_attr}")
                                break
                        
                        if current_page_elem:
                            # Try to get the next sibling
                            try:
                                # JavaScript로 현재 페이지 다음 링크 찾기
                                next_button = self.page.evaluate("""
                                    (element) => {
                                        const nextSibling = element.nextElementSibling;
                                        return nextSibling && nextSibling.tagName.toLowerCase() === 'a' ? nextSibling : null;
                                    }
                                """, current_page_elem)
                                if next_button:
                                    print("Found next button as sibling of current page element")
                            except Exception as e:
                                print(f"Error finding next sibling: {e}")
                                
                            # 다음 페이지 버튼을 찾지 못한 경우, LF_page_link_current 다음 버튼 찾기 시도
                            if not next_button:
                                try:
                                    # 숫자 버튼들 중에서 현재 페이지 다음 버튼 찾기
                                    current_page_num = int(current_page_elem.inner_text().strip())
                                    print(f"Current page number: {current_page_num}")
                                    
                                    for elem in page_links:
                                        try:
                                            page_num = int(elem.inner_text().strip())
                                            if page_num == current_page_num + 1:
                                                next_button = elem
                                                print(f"Found next page button with number: {page_num}")
                                                break
                                        except ValueError:
                                            # 숫자가 아닌 텍스트는 무시
                                            continue
                                except Exception as e:
                                    print(f"Error finding next page by number: {e}")
                        else:
                            # Try the last link if it might be a next button
                            last_link = page_links[-1]
                            last_text = last_link.inner_text().strip()
                            if last_text not in ['처음', '첫 페이지', '<<', 'first', '맨앞']:
                                next_button = last_link
                                print(f"Using last pagination link as potential next button: {last_text}")
                    
                    if next_button:
                        # Check if the button is disabled
                        cls = next_button.get_attribute('class') or ''
                        if 'disabled' not in cls and 'none' not in cls:
                            print("Clicking next page button")
                            next_button.click()
                            self.page.wait_for_load_state("networkidle")
                            time.sleep(3)  # Additional wait for content to load
                            current_page += 1
                        else:
                            print(f"Next button is disabled (class: {cls}), reached last page")
                            has_next_page = False
                    else:
                        print("No next button found, reached last page")
                        has_next_page = False
                        
                except Exception as e:
                    print(f"Error with pagination: {e}")
                    import traceback
                    traceback.print_exc()
                    has_next_page = False
            
            # Mark category as scraped in database
            self.db.mark_category_scraped(category_id)
            self.categories_scraped += 1
            self.db.update_scraping_status(
                self.session_id, 
                categories_scraped=self.categories_scraped
            )
            
            print(f"Extracted {len(agencies_data)} agencies for category {category_name}")
            return agencies_data
            
        except Exception as e:
            print(f"Error getting agencies for category {category_name}: {e}")
            return []
    
    def get_agency_detail(self, agency_id, agency_name, agency_idx, agency_detail_url):
        """Get detailed description for an agency"""
        if not agency_detail_url:
            print(f"No detail URL for agency {agency_name}, skipping")
            return None
        
        try:
            print(f"Getting detailed description for agency: {agency_name}")
            
            # Navigate to agency detail page
            if not self.navigate_to_url(agency_detail_url, retries=2):
                print(f"Failed to navigate to agency detail page: {agency_detail_url}")
                return None
            
            # Look for the detailed description
            try:
                # Try multiple possible selectors with shorter timeout
                intro_elem = None
                selectors = [
                    "#_RST_dir > div > div.cont_main > div > div > div:nth-child(2) > div.intro",
                    "div.intro", 
                    "div[class*='intro']",
                    "div.cont_main div[class*='intro']",
                    "div.cont_main p",
                    "#_RST_dir p"
                ]
                
                # Try each selector with a short timeout
                for selector in selectors:
                    try:
                        print(f"Trying selector: {selector}")
                        intro_elem = self.page.wait_for_selector(selector, timeout=3000)
                        if intro_elem:
                            print(f"Found detail description using selector: {selector}")
                            break
                    except Exception:
                        print(f"Selector {selector} not found, trying next...")
                
                if not intro_elem:
                    print(f"All selectors failed. Taking a screenshot for debugging...")
                    # Save a screenshot for debugging
                    screenshot_path = f"{self.data_dir}/debug_{agency_idx}.png"
                    self.page.screenshot(path=screenshot_path)
                    print(f"Screenshot saved to {screenshot_path}")
                    
                    # Try one last approach - get any text content from the page
                    body_text = self.page.evaluate("""
                        () => {
                            const textContent = document.body.textContent;
                            return textContent ? textContent.substring(0, 1000) : null;
                        }
                    """)
                    if body_text:
                        # Very basic cleaning - extract likely description text
                        import re
                        cleaned_text = re.sub(r'\s+', ' ', body_text).strip()
                        print(f"Using body text as fallback: {cleaned_text[:100]}...")
                        detail_desc = cleaned_text
                    else:
                        print(f"No text content found for {agency_name}")
                        return None
                else:
                    detail_desc = intro_elem.inner_text()
                
                # Update the database with the detailed description
                self.db.update_agency_detail(agency_id, detail_desc)
                
                self.details_scraped += 1
                self.db.update_scraping_status(
                    self.session_id,
                    details_scraped=self.details_scraped
                )
                
                return detail_desc
                
            except Exception as e:
                print(f"Error getting detailed description for {agency_name}: {e}")
                import traceback
                traceback.print_exc()
                return None
                
        except Exception as e:
            print(f"Error in get_agency_detail for {agency_name}: {e}")
            return None
    
    def scrape_all_agency_details(self):
        """Scrape detailed descriptions for all agencies"""
        print("\nStarting to scrape detailed agency descriptions...")
        
        try:
            # Get all agencies without detailed descriptions
            agencies = self.db.get_agencies_without_details()
            
            if not agencies:
                print("No agencies found without detailed descriptions")
                return
            
            self.details_total = len(agencies)
            self.db.update_scraping_status(
                self.session_id,
                details_total=self.details_total
            )
            
            print(f"Found {self.details_total} agencies needing detailed descriptions")
            
            for agency in tqdm(agencies):
                agency_id, agency_name, agency_idx, agency_detail_url = agency
                
                # Get detailed description
                self.get_agency_detail(agency_id, agency_name, agency_idx, agency_detail_url)
                
                # Sleep briefly to avoid overloading the server
                time.sleep(0.5)
            
            print(f"Completed scraping detailed descriptions for {self.details_scraped}/{self.details_total} agencies")
            
        except Exception as e:
            print(f"Error in scrape_all_agency_details: {e}")
    
    def scrape_all(self):
        """Scrape all categories, agencies, and their details"""
        try:
            # First get all categories
            categories = self.get_categories()
            
            if categories:
                # Filter categories if target_categories is specified
                if self.target_categories:
                    print(f"Filtering categories to: {self.target_categories}")
                    categories = [cat for cat in categories if cat['category_name'] in self.target_categories]
                    print(f"Found {len(categories)} matching categories")
                
                # Update expected total agencies
                self.agencies_total = sum(int(cat.get('agency_count', 0)) for cat in categories)
                self.db.update_scraping_status(
                    self.session_id, 
                    agencies_total=self.agencies_total
                )
                
                # Iterate through each category
                for category in categories:
                    category_id = category['id']
                    category_name = category['category_name']
                    category_url = category['category_link']
                    
                    # Scrape agencies for this category
                    self.get_agencies_in_category(category_id, category_name, category_url)
                
                # Scrape detailed descriptions for all agencies if not skipped
                if not self.skip_details:
                    self.scrape_all_agency_details()
                else:
                    print("Skipping detailed descriptions as requested")
                
                # Export all data to CSV files
                self.db.export_to_csv(self.data_dir)
                
                # Update scraping status
                self.db.update_scraping_status(
                    self.session_id, 
                    status='completed'
                )
                
                print("Scraping completed successfully!")
            
            else:
                print("No categories found to scrape.")
                self.db.update_scraping_status(
                    self.session_id, 
                    status='failed'
                )
        
        except Exception as e:
            print(f"Error in scrape_all: {e}")
            self.db.update_scraping_status(
                self.session_id, 
                status='failed'
            )
        
        finally:
            # Close the browser
            self.close()
    
    def close(self):
        """Close the browser and database"""
        if hasattr(self, 'context') and self.context:
            self.context.close()
        if hasattr(self, 'browser') and self.browser:
            self.browser.close()
        if hasattr(self, 'playwright') and self.playwright:
            self.playwright.stop()
            print("Browser closed.")
        
        if hasattr(self, 'db') and self.db:
            self.db.close()
            print("Database connection closed.")


if __name__ == "__main__":
    # Create scraper instance (set headless=True for production)
    scraper = IBossScraper(headless=False)
    
    try:
        # Run the complete scraping process
        scraper.scrape_all()
    except Exception as e:
        print(f"Error running scraper: {e}")
        scraper.close()