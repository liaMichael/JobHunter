import json
import os
import sys

# Terminal color codes for clean, colorized output
class Colors:
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    CYAN = '\033[96m'
    MAGENTA = '\033[95m'
    RESET = '\033[0m'

# Ensure the scraper and project modules can be imported by adding the parent directory to sys.path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from scrapers import default_scraper

# Custom exception to stop the execution immediately after capturing 2 jobs
class MaxJobsReached(Exception):
    pass

def run_tester(companies_to_test, num_jobs=2, use_filtering=True, job_types=None, field_keywords=None, debug_ops=None):
    """
    A local tester that iterates over a list of companies, bypasses MongoDB and Telegram,
    and stops processing a company once {num_jobs} valid jobs are found.
    """
    # Load the scraper settings from the JSON configuration file
    try:
        with open("targets.json", "r", encoding="utf-8") as f:
            targets = json.load(f)
    except FileNotFoundError:
        print(f"{Colors.RED}Error: targets.json not found in the current directory.{Colors.RESET}")
        return

    for company in companies_to_test:
        # Extract the specific company settings from the loaded targets
        target = next((t for t in targets if t["company_name"] == company), None)
        if not target:
            print(f"{Colors.YELLOW}Warning: Company '{company}' not found in targets.json. Skipping...{Colors.RESET}")
            continue

        print(f"\n{Colors.CYAN}{'='*50}")
        print(f"Starting TEST for: {company}")
        print(f"Smart Filtering: {'ENABLED' if use_filtering else 'DISABLED'}")
        print(f"Showing in browser: {'DISABLED' if debug_ops["headless"] else 'ENABLED'}")
        print(f"{'='*50}{Colors.RESET}")

        collected_jobs = []

        # --- Monkey Patching ---
        # Temporarily replace the real Telegram alert function with a local mock function
        def mock_send_job_alert(title, link, comp):
            collected_jobs.append({"title": title, "link": link})
            print(f"{Colors.GREEN}[TEST CAPTURE {len(collected_jobs)}/{num_jobs}]")
            print(f"   Title: {title}")
            print(f"   Link:  {link}{Colors.RESET}\n")
            
            # If we reached the limit of {num_jobs} jobs, raise the exception to break out 
            # of the BeautifulSoup parsing loop and move on to the next company
            if len(collected_jobs) >= num_jobs:
                raise MaxJobsReached()

        # Save the original Telegram function reference and override it in memory
        original_send_job_alert = default_scraper.send_job_alert
        default_scraper.send_job_alert = mock_send_job_alert

        # Assign filters if enabled
        j_types = job_types if use_filtering else None
        f_keywords = field_keywords if use_filtering else None

        try:
            # Execute the scraper. 
            # Passing db_collection=None ensures the scraper ignores the MongoDB history 
            # and treats every parsed job as a brand new one.
            default_scraper.scrape_company_jobs(
                company_name=target["company_name"],
                jobs_url=target["jobs_url"],
                job_container_class=target["job_container_class"],
                job_link_prefix=target.get("job_link_prefix", ""),
                link_contains=target.get("link_contains", ""),
                job_types=j_types,
                field_keywords=f_keywords,
                popup_selector=target.get("popup_selector"),
                inner_title_selector=target.get("inner_title_selector"),
                pagination_selector=target.get("pagination_selector"),
                required_locations=target.get("required_locations"),
                wait_until_mode=target.get("wait_until", "domcontentloaded"),
                db_collection=None,
                filter_clicks=target.get("filter_clicks"),
                debug_mode=debug_ops
            )
        except MaxJobsReached:
            print(f"{Colors.YELLOW}Reached the limit of {num_jobs} jobs for {company}. Stopping HTML parser.{Colors.RESET}")
        except Exception as e:
            print(f"{Colors.RED}Error during test for {company}: {e}{Colors.RESET}")
        finally:
            # Safely restore the original Telegram function to avoid affecting subsequent runs
            default_scraper.send_job_alert = original_send_job_alert

        print(f"{Colors.MAGENTA}Summary for {company}: Found {len(collected_jobs)} matching jobs.{Colors.RESET}")


if __name__ == "__main__":
    # List of companies you want to test right now
    COMPANIES_TO_TEST = [
        "RedHat"
    ]

    num_jobs_to_capture = 2 # Number of jobs to capture before stopping the test
    
    # Test filters directly in the tester
    TEST_JOB_TYPES = ["student", "intern", "סטודנט"]
    TEST_FIELD_KEYWORDS = ["software", "developer", "backend", "python", "c", "java"]
    
    # Enable keyword filtering? (True / False)
    USE_FILTERING = False

    DEBUG_OPS = {"headless": True, "clicks": False, "jobs_html": False, "pagination": False}
    
    run_tester(COMPANIES_TO_TEST, num_jobs=num_jobs_to_capture, use_filtering=USE_FILTERING, job_types=TEST_JOB_TYPES, field_keywords=TEST_FIELD_KEYWORDS, debug_ops=DEBUG_OPS)