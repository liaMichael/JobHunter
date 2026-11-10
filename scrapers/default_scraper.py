import os
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright
import sys
import re

# Add the parent directory to the system path to allow importing from 'notifiers'
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from notifiers.telegram_api import send_job_alert

def scrape_company_jobs(company_name, jobs_url, job_container_class, job_link_prefix="", link_contains="", keywords=None, popup_selector=None, inner_title_selector=None, wait_until_mode="domcontentloaded", db_collection=None):
    """
    Scrapes a company's career page using Playwright to handle dynamic JavaScript loading.
    """
    print(f"Starting scrape for {company_name}...")
    
    html_content = ""
    try:
        with sync_playwright() as p:
            # 1. Launch with arguments that hide automation flags from WAFs
            browser = p.chromium.launch(
                headless=True,
                args=["--disable-blink-features=AutomationControlled"]
            )
            
            # 2. Add viewport size to look like a real desktop user
            context = browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                viewport={"width": 1920, "height": 1080}
            )
            page = context.new_page()
            
            # 3. Inject a script to erase the 'webdriver' fingerprint before Rafael can see it
            page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            
            # Uses the dynamic wait mode (networkidle for SPAs, domcontentloaded for the rest)
            page.goto(jobs_url, wait_until=wait_until_mode, timeout=60000)

            # Handle popups/cookie banners if a selector is provided
            if popup_selector:
                try:
                    page.wait_for_selector(popup_selector, timeout=5000)
                    page.click(popup_selector)
                    page.wait_for_timeout(2000) # Wait for the popup to close and jobs to load
                except Exception:
                    pass # Popup didn't appear, move on smoothly
            
            # Convert class name to a valid CSS selector (e.g., "class1 class2" -> ".class1.class2")
            css_selector = "." + ".".join(job_container_class.split())
            
            # Wait explicitly for the job elements to render on the screen
            try:
                page.wait_for_selector(css_selector, timeout=20000)
            except Exception:
                # Print timeout error in red
                print(f"\033[91mTimeout waiting for job elements for {company_name}. The page might be empty or layout changed.\033[0m")
            
            # Short additional wait to ensure lazy-loaded React elements finish rendering completely
            page.wait_for_timeout(3000)
            
            html_content = page.content()
            browser.close()
    except Exception as e:
        # Print general Playwright error in red
        print(f"\033[91mError fetching URL for {company_name} with Playwright: {e}\033[0m")
        return

    if not html_content:
        return

    # Parse the fully rendered HTML
    soup = BeautifulSoup(html_content, 'html.parser')
    
    # 1. Find standard links, nested links, or container div itself
    job_elements = soup.select(f"a{css_selector}, {css_selector} a, {css_selector}")
    
    new_jobs_found = False

    for job in job_elements:
        href = None

        # Try standard <a> tag extraction
        if job.name == 'a' and job.has_attr('href'):
            href = job['href']
        elif job.parent and job.parent.name == 'a' and job.parent.has_attr('href'):
            # The selected element is inside the <a> tag (e.g., WeDev / Greenhouse)
            href = job.parent['href']
        else:
            a_tag = job.find('a')
            if a_tag and a_tag.has_attr('href'):
                href = a_tag['href']

        # Fallback for SPA (React/Angular/MUI/Custom) sites without <a> tags
        if not href:
            if job.has_attr('data-attr'): # Ness Technologies
                href = f"/{job['data-attr']}"
            elif job.has_attr('data-job-id'): # NGsoft
                href = f"/{job['data-job-id']}"
            else:
                text = job.get_text()
                # Search for a 4 to 6 digit job ID in the job's text
                match = re.search(r'(\d{4,6})', text)
                if match:
                    href = f"/{match.group(1)}"
        
        # Smart title extraction utilizing the new inner_title_selector
        if inner_title_selector:
            title_element = job.select_one(inner_title_selector)
            title = title_element.get_text(strip=True) if title_element else job.get_text(strip=True)
        else:
            # Fallback to standard extraction (Elbit: h3, NGsoft: h2, Ness: .il-title)
            title_element = job.find(class_='il-title') or job.find('h3') or job.find('h2')
            title = title_element.get_text(strip=True) if title_element else job.get_text(strip=True)
        
        # Clean up the "Learn more about " prefix if it exists
        if title.startswith("Learn more about "):
            title = title.replace("Learn more about ", "")
        
        # If there's no title at all, it's not a real job element
        if not title:
            continue

        # Filter by Telegram keywords (if keywords exist)
        if keywords:
            title_lower = title.lower()
            if not any(word.lower() in title_lower for word in keywords):
                continue

        # Process the final link based on whether href was found or missing (Workday)
        if href:
            # Filter links based on the required text to avoid generic buttons
            if link_contains and link_contains not in href:
                continue
            
            # Convert relative URLs to absolute URLs if needed
            if not href.startswith('http'):
                full_link = job_link_prefix.rstrip('/') + '/' + href.lstrip('/')
            else:
                full_link = href
        else:
            # Fallback: If the link is hidden (like in Marvell's Workday system), use the general search URL
            full_link = jobs_url

        # Create a unique identifier to prevent duplicate alerts
        job_id = f"{company_name}_{title}"
        
        # Check if the job already exists in the database
        is_seen = False
        if db_collection is not None:
            is_seen = db_collection.find_one({"_id": job_id}) is not None

        if not is_seen:
            print(f"New job found: {title}")
            send_job_alert(title, full_link, company_name)
            
            # Insert the new job into MongoDB
            if db_collection is not None:
                db_collection.insert_one({
                    "_id": job_id,
                    "company": company_name,
                    "title": title
                })
            new_jobs_found = True
        
    if new_jobs_found:
        print(f"Finished scrape for {company_name}: New jobs were added to the database.")
    else:
        print(f"Finished scrape for {company_name}: No new jobs found.")