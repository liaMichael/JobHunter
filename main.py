import os
import sys
import json
from dotenv import load_dotenv
from scrapers.default_scraper import scrape_company_jobs
from notifiers.telegram_api import process_telegram_commands, load_preferences

# Ensure the project root is in the path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Load environment variables
load_dotenv()
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

def main():
    print("Starting JobHunter...")

    # Process Telegram commands and update preferences before scraping
    if TELEGRAM_TOKEN and CHAT_ID:
        print("Checking Telegram for new commands...")
        process_telegram_commands(TELEGRAM_TOKEN, CHAT_ID)

    # Load the active filtering keywords
    prefs = load_preferences()
    keywords = prefs.get("keywords", [])
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
            keywords=keywords  # <-- Pass the keywords to the scraper
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