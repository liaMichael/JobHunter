import os
import sys
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
    targets = [
        {
            "company_name": "Google",
            "jobs_url": "https://www.google.com/about/careers/applications/jobs/results?location=Israel", 
            "job_title_class": "WpHeLc VfPpkd-mRLv6 VfPpkd-RLmnJb",
            "job_link_prefix": "https://www.google.com/about/careers/applications",
            "link_contains": "jobs/results/"
        },
        {
            "company_name": "Amazon",
            "jobs_url": "https://amazon.jobs/content/en/locations/israel/tel-aviv", 
            "job_title_class": "header-module_desktop__Dnj66 header-module_title__9-W3R",
            "job_link_prefix": "https://amazon.jobs/en",
            "link_contains": "/jobs/"
        },
        {
            "company_name": "Amazon Annapurna Labs",
            "jobs_url": "https://amazon.jobs/content/en/teams/annapurna-labs?country%5B%5D=IL#search", 
            "job_title_class": "header-module_title__9-W3R",
            "job_link_prefix": "https://amazon.jobs/en",
            "link_contains": "/jobs/"
        },
        {
            "company_name": "Intel",
            "jobs_url": "https://intel.wd1.myworkdayjobs.com/External?locations=1e4a4eb3adf101ad7f35e278bf812cd1&locations=1e4a4eb3adf101aaeda8a474bf818ecd&locations=1e4a4eb3adf101f41cd29774bf8184cd&locations=1e4a4eb3adf1013563ba9174bf817fcd&locations=6dc05d901d65100158f5ba48aafb0000&locations=1e4a4eb3adf101cb242c9e74bf8189cd",
            "job_title_class": "css-19uc56f",
            "job_link_prefix": "https://intel.wd1.myworkdayjobs.com",
            "link_contains": "/job/"
        },
        {
            "company_name": "SAP",
            "jobs_url": "https://jobs.sap.com/en/jobs/?country=Israel",
            "job_title_class": "text-job-card-title",
            "job_link_prefix": "https://jobs.sap.com", 
            "link_contains": "/jobs/",
            "popup_selector": "#truste-consent-button"
        },
        {
            "company_name": "Microsoft",
            "jobs_url": "https://apply.careers.microsoft.com/careers?hl=en&start=0&location=Israel&pid=1970393557038901&sort_by=distance&filter_include_remote=1&filter_include_relocation=0", 
            "job_title_class": "r-link card-F1ebU",
            "job_link_prefix": "https://apply.careers.microsoft.com",
            "link_contains": "/careers/job/"
        },
        {
            "company_name": "NVIDIA",
            "jobs_url": "https://jobs.nvidia.com/careers?domain=nvidia.com&hl=he&start=0&location=Israel&pid=893393561562&sort_by=timestamp&filter_include_remote=1&filter_include_relocation=0", 
            "job_title_class": "r-link card-F1ebU",
            "job_link_prefix": "https://jobs.nvidia.com", 
            "link_contains": "/careers/job/"
        },
        {
            "company_name": "Apple",
            "jobs_url": "https://jobs.apple.com/en-il/search?location=israel-ISR", 
            "job_title_class": "link-inline t-intro word-wrap-break-word more",
            "job_link_prefix": "https://jobs.apple.com", 
            "link_contains": "/details/"
        },
        {
            "company_name": "IAI",
            "jobs_url": "https://jobs.iai.co.il/jobs/", 
            "job_title_class": "vue-job job-card",
            "job_link_prefix": "https://jobs.iai.co.il", 
            "link_contains": "/job/"
        },
        {
            "company_name": "Elbit Systems",
            "jobs_url": "https://elbitsystemscareer.com/jobs/", 
            "job_title_class": "MuiCard-root",
            "job_link_prefix": "https://elbitsystemscareer.com",
            "link_contains": ""
        },
        # {
        #     "company_name": "Rafael",
        #     "jobs_url": "https://career.rafael.co.il/search/1/", 
        #     "job_title_class": "item-title",
        #     "job_link_prefix": "https://career.rafael.co.il/job", 
        #     "link_contains": "/job/"
        # },
        {
            "company_name": "WeDev",
            "jobs_url": "https://job-boards.eu.greenhouse.io/wedev?gh_src=wp878wt2teu", 
            "job_title_class": "body--medium",
            "job_link_prefix": "https://job-boards.eu.greenhouse.io",
            "link_contains": "/jobs/"
        },
        {
            "company_name": "Earnix",
            "jobs_url": "https://earnix.com/our-story/careers/israel/#open-positions", 
            "job_title_class": "typo-h4",
            "job_link_prefix": "https://earnix.com", 
            "link_contains": "/career/"
        },
        {
            "company_name": "Ness Technologies",
            "jobs_url": "https://www.ness-tech.co.il/careers/", 
            "job_title_class": "card-job-container",
            "job_link_prefix": "https://www.ness-tech.co.il/careers",
            "link_contains": ""
        },
        # {
        #     "company_name": "NGsoft",
        #     "jobs_url": "https://www.ngsoft.com/who-we-are/careers", 
        #     "job_title_class": "item",
        #     "job_link_prefix": "",
        #     "link_contains": ""
        # }
        {
            "company_name": "Marvell Technology",
            "jobs_url": "https://marvell.wd1.myworkdayjobs.com/MarvellCareers/2/refreshFacet/318c8bb6f553100021d223d9780d30be", 
            "job_title_class": "gwt-Label",
            "job_link_prefix": "", 
            "link_contains": ""
        }
        # You can add more companies using the same structure...
    ]
    
    # Run scrapers with the keyword filter
    for target in targets:
        scrape_company_jobs(
            company_name=target["company_name"],
            jobs_url=target["jobs_url"],
            job_title_class=target["job_title_class"],
            job_link_prefix=target.get("job_link_prefix", ""),
            link_contains=target.get("link_contains", ""),
            keywords=keywords  # <-- Pass the keywords to the scraper
        )
        
    print("JobHunter finished running.")

if __name__ == "__main__":
    main()