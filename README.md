# I-Boss Agency Directory Scraper

This tool scrapes the agency directory from the i-boss.co.kr website, extracting:

1. All agency categories with their links and agency counts
2. All agencies within each category (name, URL, logo, description)
3. Detailed descriptions from each agency's individual page
4. Agency logos saved as image files in a dedicated directory

The data is stored in a SQLite database, allowing for parallel access to the scraped data while the scraping process is running.

## Requirements

- Python 3.7+
- Playwright (automatically installs browsers)
- SQLite3 (included in Python standard library)
- pandas (for CSV export)
- tqdm (for progress bars)
- requests (for logo downloads)

## Installation

1. Install required packages:
```
pip install -r requirements.txt
```

2. Install Playwright browsers:
```
playwright install
```

## Usage

### Running the Scraper

Run the scraper with command-line arguments:
```
python main.py -c "category_name1" "category_name2" -n 10 -o "output_dir" -d "database_path" -s --headless
```

Arguments:
- `-c, --categories`: Specific categories to scrape (default: all categories)
- `-n, --num-agencies`: Maximum number of agencies to scrape per category (default: all)
- `-o, --output-dir`: Directory for output files (default: "iboss_data")
- `-d, --db-path`: Path for the SQLite database (default: "iboss_scraper.db")
- `-s, --skip-details`: Skip scraping detailed descriptions (default: False)
- `--headless`: Run browser in headless mode (default: False)

For example, to scrape just 5 agencies from the "페이스북" and "종합광고대행사" categories:
```
python main.py -c 페이스북 종합광고대행사 -n 5
```

### Accessing the Data While Scraping

While the scraper is running, you can independently access the data using the database directly:

```python
from iboss_scraper import Database

db = Database("path/to/iboss_scraper.db")
categories = db.get_categories()
agencies = db.get_all_agencies()
```

## Technical Details

### Architecture Overview

The scraper is built around two main classes:

1. `Database`: Handles all database operations with thread-safety
2. `IBossScraper`: Manages browser automation and scraping logic

### Database Class

The `Database` class is a wrapper around SQLite with the following key features:

#### Table Structure
- **categories**: Stores category information
  - `id`: Primary key
  - `category_name`: Name of the category
  - `category_link`: URL to the category page
  - `agency_count`: Number of agencies in this category
  - `scraped`: Boolean flag indicating if category has been scraped
  - `last_updated`: Timestamp of last update

- **agencies**: Stores agency information
  - `id`: Primary key
  - `category_id`: Foreign key to categories table
  - `category_name`: Name of the category
  - `agency_name`: Name of the agency
  - `agency_url`: URL of the agency's website
  - `agency_logo`: URL to the agency's logo on i-boss
  - `local_logo_path`: Local path where logo image is stored
  - `agency_desc`: Short description of the agency
  - `agency_idx`: Agency index used in URL construction
  - `agency_detail_url`: URL to the agency's detail page
  - `agency_detail_desc`: Detailed description from the agency's page
  - `detailed_scraped`: Boolean flag indicating if details have been scraped
  - `last_updated`: Timestamp of last update

- **scraping_status**: Tracks scraping progress
  - `id`: Primary key
  - `session_start`: Timestamp when scraping started
  - `session_end`: Timestamp when scraping ended
  - `categories_total`: Total number of categories to scrape
  - `categories_scraped`: Number of categories scraped
  - `agencies_total`: Total number of agencies to scrape
  - `agencies_scraped`: Number of agencies scraped
  - `details_total`: Total number of agency details to scrape
  - `details_scraped`: Number of agency details scraped
  - `status`: Current status of scraping (running, completed, failed)

#### Key Methods

- `_create_tables()`: Initializes database schema if tables don't exist
- `insert_category(category_name, category_link, agency_count)`: Inserts or updates a category
- `insert_agency(category_id, ...)`: Inserts or updates an agency
- `update_agency_detail(agency_id, detail_desc)`: Adds detailed description to an agency
- `get_agencies_without_details()`: Returns agencies that need detailed descriptions
- `mark_category_scraped(category_id)`: Marks a category as completely scraped
- `start_scraping_session()`: Initializes a new scraping session
- `update_scraping_status(...)`: Updates progress statistics
- `export_to_csv(export_dir)`: Exports all data to CSV files

### IBossScraper Class

This is the main class that handles the web scraping using Playwright.

#### Initialization

```python
def __init__(self, headless=False, db_path="iboss_data/iboss_scraper.db", 
             target_categories=None, max_agencies_per_category=0, 
             skip_details=False, output_dir="iboss_data"):
```

- `headless`: Whether to run the browser in headless mode
- `db_path`: Path to SQLite database
- `target_categories`: List of specific categories to scrape (None = all)
- `max_agencies_per_category`: Limit on agencies per category (0 = no limit)
- `skip_details`: Whether to skip scraping detailed descriptions
- `output_dir`: Directory for output files and logos

#### Key Methods

- `navigate_to_url(url, retries=3)`: Handles page navigation with retry logic
- `get_categories()`: Scrapes all category information from the main directory page
- `extract_agency_idx(href)`: Extracts agency ID from URL for detailed page construction
- `download_logo(logo_url, category_name, agency_name)`: Downloads and saves agency logo
- `get_agencies_in_category(category_id, category_name, category_url)`: Scrapes all agencies in a category
- `get_agency_detail(agency_id, agency_name, agency_idx, agency_detail_url)`: Scrapes detailed description
- `scrape_all_agency_details()`: Scrapes details for all agencies without details
- `scrape_all()`: Main method that orchestrates the complete scraping process
- `close()`: Cleans up browser and database resources

#### Scraping Process Flow

1. **Category Extraction**:
   - Navigates to the main directory page
   - Finds all category elements using CSS selectors
   - Extracts name, link, and agency count
   - Inserts data into the database

2. **Agency Extraction (per category)**:
   - Navigates to the category page
   - Identifies agency list elements
   - For each agency:
     - Extracts name, URL, logo URL, and description
     - Downloads the agency logo to local storage
     - Constructs detail page URL from agency index
     - Handles pagination to process all pages
   - Marks category as scraped when done

3. **Detail Extraction**:
   - Queries database for agencies without detailed descriptions
   - For each agency:
     - Navigates to its detail page
     - Extracts detailed description using multiple selector strategies
     - Updates database with the detailed information

4. **Data Export**:
   - Exports all tables to CSV files
   - Creates separate files for categories, agencies, and status

### Logo Download Functionality

The logo download functionality works as follows:

1. During agency extraction, when a logo URL is found, the `download_logo` method is called:

```python
def download_logo(self, logo_url, category_name, agency_name):
    """Download agency logo and save it as [category_name]_[agency_name].png"""
```

2. The method:
   - Sanitizes category and agency names to create valid filenames
   - Creates a filename in the format `[category_name]_[agency_name].png`
   - Checks if the file already exists to avoid duplicate downloads
   - Downloads the image using the `requests` library
   - Saves it to the `logos` subdirectory of the output directory
   - Returns the local file path for storage in the database

3. The local path is then stored in the `local_logo_path` field in the agencies table

### Browser Automation Details

The scraper uses Playwright for browser automation:

- Browser is configured with a fixed viewport size (1920x1080)
- Default page timeout is set to 30 seconds
- Selectors use a combination of direct CSS selectors and fallback strategies
- JavaScript evaluation is used for complex element interactions
- Screenshot capabilities for debugging when selectors fail
- Robust waiting strategies for dynamic content

### Threading and Concurrency

- Database operations are protected with a lock to ensure thread safety
- While the main scraping process is single-threaded, the database can be accessed concurrently

### Error Handling

- Each method has comprehensive try/except blocks
- Navigation failures are handled with retries
- Multiple selector strategies with fallbacks for element detection
- Error reporting with detailed messages and stack traces
- Graceful degradation for partial data extraction

## Output

The scraper creates:

1. A SQLite database in the specified output directory
2. CSV files exported from the database:
   - `categories.csv`: List of all agency categories with counts
   - `agencies.csv`: Combined data of all agencies across all categories
   - `scraping_status.csv`: Statistics about the scraping process
3. Downloaded agency logos in the `logos` subdirectory, named as `[category_name]_[agency_name].png`

## Performance Considerations

- The scraper uses reasonable delays to avoid overloading the target server
- Page navigation includes waiting for network idle state
- Logo downloads are performed with streaming to minimize memory usage
- Database transactions are optimized for batch operations
- Progress bars provide visual feedback for long-running operations