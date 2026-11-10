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
            # Launch with arguments that hide automation flags from WAFs
            browser = p.chromium.launch(
                headless=True,
                args=["--disable-blink-features=AutomationControlled"]
            )
            
            # Add viewport size to look like a real desktop user
            context = browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                viewport={"width": 1920, "height": 1080}
            )
            page = context.new_page()
            
            # Inject a script to erase the 'webdriver' fingerprint before Rafael can see it
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
            
            # Convert class name to a valid CSS selector and escape Tailwind colons (e.g., hover:text-blue -> hover\:text-blue)
            css_selector = "." + ".".join(job_container_class.split()).replace(":", r"\:")
            
            # Wait explicitly for the job elements to render on the screen
            try:
                page.wait_for_selector(css_selector, timeout=20000)
                
                # Pagination Loop: Click 'Next' and accumulate HTML from all pages
                for page_num in range(1, 30): # Safety limit to prevent infinite loops
                    page.wait_for_timeout(4000) # Give React time to render the jobs
                    
                    # Accumulate this page's HTML to our mega-document
                    html_content += page.content()
                    
                    # Look for the "Next" button handling English, Hebrew, and standard React pagination classes
                    next_btn = page.locator('button[aria-label*="Next" i], a[aria-label*="Next" i], button[aria-label*="הבא"], a[aria-label*="הבא"], ul.pagination li:last-child button, ul.pagination li:last-child a').first
                    
                    if next_btn.is_visible():
                        # React sometimes uses 'aria-disabled' instead of the native HTML 'disabled' attribute
                        is_aria_disabled = next_btn.get_attribute("aria-disabled") == "true"
                        is_native_disabled = next_btn.is_disabled()
                        
                        if not is_aria_disabled and not is_native_disabled:
                            next_btn.click()
                        else:
                            break
                    else:
                        break
                        
            except Exception:
                # Print timeout error in red
                print(f"\033[91mTimeout waiting for job elements for {company_name}.\033[0m")
            
            # Fallback if no HTML was accumulated (or for non-paginated single-page sites)
            if not html_content:
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
    
    # Find standard links, nested links, or container div itself
    job_elements = soup.select(f"a{css_selector}, {css_selector} a, {css_selector}")
    
    new_jobs_found = False
    seen_in_run = set()  # Prevent duplicate processing in a single run

    for job in job_elements:
        href = None

        # If the matched job element ITSELF is an anchor tag (e.g., Earnix)
        if job.name == 'a' and job.has_attr('href'):
            href = job['href']

        # Specialized extraction for Google and structured sites using explicit attributes (e.g., jsname="hSRGPd")
        specific_a = job.find('a', attrs={'jsname': 'hSRGPd'})
        if not href and specific_a and specific_a.has_attr('href'):
            href = specific_a['href']

        # Fallback for SPA / Custom systems without <a> tags
        if not href:
            if job.has_attr('data-attr'): # Ness legacy
                href = f"/{job['data-attr']}"
            elif job.has_attr('data-job-id'): # NGsoft
                href = f"/{job['data-job-id']}"

        # Check if the element itself or its direct parent is an anchor tag
        if not href:
            if job.name == 'a' and job.has_attr('href'):
                href = job['href']
            elif job.parent and job.parent.name == 'a' and job.parent.has_attr('href'):
                href = job.parent['href']

        # Search for any valid <a> tag inside the job container
        if not href:
            for a_tag in job.find_all('a', href=True):
                link = a_tag['href']
                if not link.startswith('#') and "javascript" not in link.lower() and "mailto" not in link.lower():
                    if link_contains and link_contains in link:
                        href = link
                        break
                    elif not href:
                        href = link

        # Specific fallback for React/Eightfold containers where the link is embedded inside the title component
        if not href:
            inner_a = job.find('a', href=True)
            if inner_a:
                href = inner_a['href']

        # Smart title extraction utilizing the new inner_title_selector
        if inner_title_selector:
            title_element = job.select_one(inner_title_selector)
            title = title_element.get_text(strip=True) if title_element else job.get_text(strip=True)
        else:
            # Fallback to standard extraction
            title_element = job.find(class_='il-title') or job.find('h3') or job.find('h2')
            title = title_element.get_text(strip=True) if title_element else job.get_text(strip=True)
        
        # Clean up prefixes if they exist
        if title.startswith("Learn more about "):
            title = title.replace("Learn more about ", "")
        
        # If there's no title at all, skip
        if not title:
            continue

        # Filter by Telegram keywords (if keywords exist)
        if keywords:
            title_lower = title.lower()
            if not any(word.lower() in title_lower for word in keywords):
                continue

        # Extract full card text to check for location validity (fixing Eightfold global spill)
        card_full_text = job.get_text()
        
        # If the company is Millennium, strictly require Israel or Tel Aviv in the card text
        if company_name == "Millennium":
            if not any(loc in card_full_text for loc in ["Israel"]):
                continue

        # Process the final link based on whether href was found or missing
        if href:
            if link_contains and link_contains not in href:
                continue
            
            if not href.startswith('http'):
                if href.startswith('?'):
                    full_link = job_link_prefix.rstrip('/') + href
                else:
                    full_link = job_link_prefix.rstrip('/') + '/' + href.lstrip('/')
            else:
                full_link = href
        else:
            # Fallback if no href was found at all: use the general search URL
            full_link = jobs_url

        # Create a unique identifier to prevent duplicate alerts
        job_id = f"{company_name}_{title}"
        
        # DEDUPLICATION FIX: Skip if already processed in this exact run
        if job_id in seen_in_run:
            continue
        seen_in_run.add(job_id)

        # Check if the job already exists in the database
        is_seen = False
        if db_collection is not None:
            is_seen = db_collection.find_one({"_id": job_id}) is not None

        if not is_seen:
            print(f"New job found: {title}")
            send_job_alert(title, full_link, company_name)
            
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