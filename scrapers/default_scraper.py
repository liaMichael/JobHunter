import os
import json
import requests
from bs4 import BeautifulSoup
import sys

# Add the parent directory to the system path to allow importing from 'notifiers'
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from notifiers.telegram_api import send_job_alert

# Define the absolute path to the JSON file to avoid path issues when running via Cron
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

def scrape_company_jobs(company_name, jobs_url, job_title_class, job_link_prefix=""):
    """
    Scrapes a company's career page for job postings, checks for new ones, 
    sends an alert, and updates the local state.
    
    :param company_name: Name of the company.
    :param jobs_url: The URL of the careers/jobs page.
    :param job_title_class: The CSS class of the HTML element containing the job title (usually an <a> tag).
    :param job_link_prefix: Prefix to add if the scraped link is a relative path.
    """
    print(f"Starting scrape for {company_name}...")
    
    try:
        # Using a standard User-Agent to prevent basic bot-blocking by websites
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
        response = requests.get(jobs_url, headers=headers, timeout=10)
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        print(f"Error fetching URL for {company_name}: {e}")
        return

    soup = BeautifulSoup(response.text, 'html.parser')
    
    # Locate all job elements based on the provided CSS class
    job_elements = soup.find_all('a', class_=job_title_class)
    
    if not job_elements:
        print(f"No jobs found for {company_name}. The class name might be wrong or the page is dynamically loaded (JS).")
        return

    seen_jobs = load_seen_jobs()
    new_jobs_found = False

    for job in job_elements:
        # Fallback to aria-label if standard text is empty
        title = job.get_text(strip=True) or job.get('aria-label', '')
        
        # Clean up the "Learn more about " prefix if it exists
        if title.startswith("Learn more about "):
            title = title.replace("Learn more about ", "")
            
        link = job.get('href')
        
        if not title or not link:
            continue

        # Convert relative URLs to absolute URLs if needed
        if not link.startswith('http'):
            # lstrip('/') prevents double slashes if prefix already ends with one
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

# Test block
if __name__ == "__main__":
    # We will test the generic logic. In reality, we will call this from main.py
    print("Testing the scraper base structure...")