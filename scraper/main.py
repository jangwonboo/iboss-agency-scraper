#!/usr/bin/env python3
import os
import time
import sys
from arg_parser import parse_args
from iboss_scraper import IBossScraper, Database

def main():
    """Main entry point for the scraper"""
    # Parse command line arguments
    args = parse_args()
    
    # Create output directory if it doesn't exist
    os.makedirs(args.output_dir, exist_ok=True)
    
    # Set database path
    db_path = os.path.join(args.output_dir, os.path.basename(args.db_path))
    
    print(f"I-Boss Agency Directory Scraper")
    print(f"===============================")
    print(f"Categories to scrape: {args.categories}")
    print(f"Agencies per category: {args.num_agencies if args.num_agencies > 0 else 'All'}")
    print(f"Headless mode: {'Yes' if args.headless else 'No'}")
    print(f"Skip detailed descriptions: {'Yes' if args.skip_details else 'No'}")
    print(f"Database path: {db_path}")
    print(f"Output directory: {args.output_dir}")
    print(f"===============================")
    
    # Initialize scraper
    scraper = IBossScraper(
        headless=args.headless,
        db_path=db_path,
        target_categories=args.categories,
        max_agencies_per_category=args.num_agencies,
        skip_details=args.skip_details,
        output_dir=args.output_dir
    )
    
    try:
        # Run the scraper
        print("\nStarting scraper...")
        scraper.scrape_all()
        
        # Export results to CSV
        print("\nExporting results to CSV...")
        db = Database(db_path)
        db.export_to_csv(args.output_dir)
        db.close()
        
        print(f"\nScraping completed successfully! Results saved to {args.output_dir}")
        
    except KeyboardInterrupt:
        print("\nScraping interrupted by user.")
        scraper.close()
        sys.exit(1)
    except Exception as e:
        print(f"\nError running scraper: {e}")
        scraper.close()
        sys.exit(1)

if __name__ == "__main__":
    main()