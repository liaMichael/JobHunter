import os
import json
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright
import sys

# Add the parent directory to the system path to allow importing from 'notifiers'
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from notifiers.telegram_api import send_job_alert

DATA_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "seen_jobs.json")

def load_seen_jobs():
    """Loads the list of already seen jobs from the JSON file."""
    if not os.path.exists(DATA_FILE):
        return []
    with open(DATA_FILE, 'r', encoding='utf-8') as f:
        try:
            return json.load(f)
        except json.JSONDecodeError:
            return []

def save_seen_jobs(seen_jobs):
    """Saves the updated list of seen jobs to the JSON file."""
    os.makedirs(os.path.dirname(DATA_FILE), exist_ok=True)
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(seen_jobs, f, ensure_ascii=False, indent=4)

def scrape_company_jobs(company_name, jobs_url, job_title_class, job_link_prefix="", link_contains=""):
    """
    Scrapes a company's career page using Playwright to handle dynamic JavaScript loading.
    """
    print(f"Starting scrape for {company_name}...")
    
    html_content = ""
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            
            # Changed from 'networkidle' to 'domcontentloaded' to avoid infinite timeouts
            page.goto(jobs_url, wait_until='domcontentloaded', timeout=60000)
            
            # Convert class name to a valid CSS selector (e.g., "class1 class2" -> ".class1.class2")
            css_selector = "." + ".".join(job_title_class.split())
            
            # Wait explicitly for the job elements to render on the screen
            try:
                page.wait_for_selector(css_selector, timeout=20000)
            except Exception:
                print(f"Timeout waiting for job elements for {company_name}. The page might be empty or layout changed.")
            
            # Short additional wait to ensure lazy-loaded React elements finish rendering completely
            page.wait_for_timeout(3000)
            
            html_content = page.content()
            browser.close()
    except Exception as e:
        print(f"Error fetching URL for {company_name} with Playwright: {e}")
        return

    if not html_content:
        return

    # Parse the fully rendered HTML
    soup = BeautifulSoup(html_content, 'html.parser')
    
    # Split the class string into a list to match multiple classes accurately
    class_list = job_title_class.split()
    job_elements = soup.find_all('a', class_=class_list)
    
    seen_jobs = load_seen_jobs()
    new_jobs_found = False

    for job in job_elements:
        title = job.get_text(strip=True) or job.get('aria-label', '')
        
        # Clean up the "Learn more about " prefix if it exists
        if title.startswith("Learn more about "):
            title = title.replace("Learn more about ", "")
            
        link = job.get('href')
        
        if not title or not link:
            continue

        # Filter links based on the required text to avoid generic buttons
        if link_contains and link_contains not in link:
            continue

        # Convert relative URLs to absolute URLs if needed
        if not link.startswith('http'):
            link = job_link_prefix.rstrip('/') + '/' + link.lstrip('/')
        
        # Create a unique identifier to prevent duplicate alerts
        job_id = f"{company_name}_{title}"
        
        if job_id not in seen_jobs:
            print(f"New job found: {title}")
            send_job_alert(title, link, company_name)
            seen_jobs.append(job_id)
            new_jobs_found = True
        
    if new_jobs_found:
        save_seen_jobs(seen_jobs)
        print(f"Finished scrape for {company_name}: New jobs were added and saved.")
    else:
        print(f"Finished scrape for {company_name}: No new jobs found.")