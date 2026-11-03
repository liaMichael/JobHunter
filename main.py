import os
import sys

# Ensure the project root is in the path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from scrapers.default_scraper import scrape_company_jobs

def main():
    print("Starting JobHunter...")
    
    # List of career pages to monitor
    targets = [
        {
            "company_name": "Google",
            "jobs_url": "https://www.google.com/about/careers/applications/jobs/results?location=Israel", 
            "job_title_class": "WpHeLc VfPpkd-mRLv6 VfPpkd-RLmnJb",
            "job_link_prefix": "https://www.google.com/about/careers/applications/",
            "link_contains": "jobs/results/" # Added filter to ensure it's a real job link
        }
    ]
    
    for target in targets:
        scrape_company_jobs(
            company_name=target["company_name"],
            jobs_url=target["jobs_url"],
            job_title_class=target["job_title_class"],
            job_link_prefix=target.get("job_link_prefix", ""),
            link_contains=target.get("link_contains", "")
        )
        
    print("JobHunter finished running.")

if __name__ == "__main__":
    main()