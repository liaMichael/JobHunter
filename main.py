import os
import sys
import json
import concurrent.futures
from dotenv import load_dotenv
from pymongo import MongoClient
from scrapers.default_scraper import scrape_company_jobs

# Ensure the project root is in the path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Load environment variables
load_dotenv()
MONGO_URI = os.getenv("MONGO_URI")

# A wrapper function to handle a single target for multi-threading
def run_scraper_task(target, job_types, field_keywords, db_collection):
    try:
        scrape_company_jobs(
            company_name=target["company_name"],
            jobs_url=target["jobs_url"],
            job_container_class=target.get("job_container_class", ""),
            job_link_prefix=target.get("job_link_prefix", ""),
            link_contains=target.get("link_contains", ""),
            job_types=job_types,
            field_keywords=field_keywords,
            popup_selector=target.get("popup_selector"),
            inner_title_selector=target.get("inner_title_selector"),
            pagination_selector=target.get("pagination_selector"),
            required_locations=target.get("required_locations"),
            wait_until_mode=target.get("wait_until", "domcontentloaded"),
            db_collection=db_collection,
            filter_clicks=target.get("filter_clicks")
        )
    except Exception as e:
        print(f"Failed to scrape {target.get('company_name')}: {e}")

def main():
    print("Starting JobHunter...")

    seen_jobs_collection = None
    
    # Default lists (clean core words)
    job_types = ["student", "intern", "סטודנט"]
    field_keywords = ["software", "developer", "backend", "python", "c", "java"]

    # Initialize MongoDB connection
    if MONGO_URI:
        client = MongoClient(MONGO_URI)
        db = client["jobhunter_db"]
        seen_jobs_collection = db["seen_jobs"]
        print("Successfully connected to MongoDB.")

        # Retrieve keywords directly from MongoDB instead of a local file
        prefs_collection = db["preferences"]
        prefs_doc = prefs_collection.find_one({"_id": "keywords"})
        
        if prefs_doc:
            if "job_types" in prefs_doc:
                job_types = prefs_doc["job_types"]
            if "field_keywords" in prefs_doc:
                field_keywords = prefs_doc["field_keywords"]
    else:
        print("\033[93mWarning: MONGO_URI not found. Running without database.\033[0m")

    print(f"Active Job Types: {job_types}")
    print(f"Active Field Keywords: {field_keywords}")
    
    # List of career pages to monitor
    targets = load_targets()
    
    # Parallel execution configuration
    MAX_WORKERS = 4
    print(f"Starting parallel scraping with {MAX_WORKERS} workers...")
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        # Submit tasks to the background threads
        futures = [
            executor.submit(run_scraper_task, target, job_types, field_keywords, seen_jobs_collection) 
            for target in targets
        ]
        
        # Yield futures as they finish to catch exceptions
        for future in concurrent.futures.as_completed(futures):
            try:
                future.result()
            except Exception as exc:
                print(f"A scraper thread generated an exception: {exc}")
        
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
