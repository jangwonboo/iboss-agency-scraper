import argparse
import os

def parse_args():
    """Parse command line arguments for the scraper"""
    
    parser = argparse.ArgumentParser(description='I-Boss Agency Directory Scraper')
    
    # Categories to scrape
    parser.add_argument(
        '-c', '--categories', 
        nargs='+', 
        default=['종합광고대행사', '페이스북'], 
        help='Categories to scrape (default: 종합광고대행사 페이스북)'
    )
    
    # Number of agencies per category
    parser.add_argument(
        '-n', '--num-agencies', 
        type=int, 
        default=3, 
        help='Maximum number of agencies to scrape per category (default: 3, use 0 for all)'
    )
    
    # Headless mode
    parser.add_argument(
        '--headless', 
        action='store_true',
        help='Run browser in headless mode'
    )
    
    # Skip detailed descriptions
    parser.add_argument(
        '--skip-details', 
        action='store_true',
        help='Skip scraping detailed descriptions'
    )
    
    # Database path
    parser.add_argument(
        '--db-path', 
        default='./iboss_scraper.db',
        help='Path to SQLite database file (default: ./iboss_scraper.db)'
    )
    
    # Output directory for CSV files
    parser.add_argument(
        '--output-dir', 
        default='.',
        help='Directory to store CSV output files (default: current directory)'
    )
    
    return parser.parse_args()


if __name__ == "__main__":
    # Test the argument parser
    args = parse_args()
    print(f"Categories to scrape: {args.categories}")
    print(f"Agencies per category: {args.num_agencies}")
    print(f"Headless mode: {args.headless}")
    print(f"Skip details: {args.skip_details}")
    print(f"Database path: {args.db_path}")
    print(f"Output directory: {args.output_dir}")