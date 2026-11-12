import os
import sys
import json
from dotenv import load_dotenv
from pymongo import MongoClient
from scrapers.default_scraper import scrape_company_jobs

# Ensure the project root is in the path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Load environment variables
load_dotenv()
MONGO_URI = os.getenv("MONGO_URI")

def main():
    print("Starting JobHunter...")

    seen_jobs_collection = None
    keywords = ["student", "intern", "software", "סטודנט"] # Default keywords

    # Initialize MongoDB connection
    if MONGO_URI:
        client = MongoClient(MONGO_URI)
        db = client["jobhunter_db"]
        seen_jobs_collection = db["seen_jobs"]
        print("Successfully connected to MongoDB.")
        
        # Retrieve keywords directly from MongoDB instead of a local file
        prefs_collection = db["preferences"]
        prefs_doc = prefs_collection.find_one({"_id": "keywords"})
        
        if prefs_doc and "words" in prefs_doc:
            keywords = prefs_doc["words"]
    else:
        print("\033[93mWarning: MONGO_URI not found. Running without database.\033[0m")

    print(f"Active filtering keywords: {keywords}")
    
    # List of career pages to monitor
    targets = load_targets()
    
    # Run scrapers with the keyword filter
    for target in targets:
        scrape_company_jobs(
            company_name=target["company_name"],
            jobs_url=target["jobs_url"],
            job_container_class=target["job_container_class"],
            job_link_prefix=target.get("job_link_prefix", ""),
            link_contains=target.get("link_contains", ""),
            keywords=keywords,
            popup_selector=target.get("popup_selector"),
            inner_title_selector=target.get("inner_title_selector"),
            wait_until_mode=target.get("wait_until", "domcontentloaded"),
            db_collection=seen_jobs_collection,
            filter_clicks=target.get("filter_clicks")
        )
        
    print("JobHunter finished running.")

def load_targets(filepath="targets.json"):
    try:
        with open(filepath, 'r', encoding='utf-8') as file:
            return json.load(file)
    except FileNotFoundError:
        print(f"\033[91mError: Configuration file '{filepath}' not found!\033[0m")
        return []
    except json.JSONDecodeError as e:
        print(f"\033[91mError parsing JSON file: {e}\033[0m")
        return []

if __name__ == "__main__":
    main()