import os
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright
import sys
import re
import hashlib

# Add the parent directory to the system path to allow importing from 'notifiers'
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from notifiers.telegram_api import send_job_alert

# Terminal color codes for clean, colorized output
class Colors:
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    CYAN = '\033[96m'
    MAGENTA = '\033[95m'
    RESET = '\033[0m'

def scrape_company_jobs(company_name, jobs_url, job_container_class="", job_link_prefix="", link_contains="", job_types=None, field_keywords=None, popup_selector=None, pagination_selector=None, inner_title_selector=None, wait_until_mode="domcontentloaded", db_collection=None, filter_clicks=None, required_locations=None, debug_mode=None):
    """
    Scrapes a company's career page using Playwright to handle dynamic JavaScript loading.
    """
    if debug_mode is None:
        debug_mode = {"headless": True, "clicks": False, "jobs_html": False}

        
    print(f"Starting scrape for {company_name}...")
    
    html_content = ""
    try:
        with sync_playwright() as p:
            # Launch with arguments that hide automation flags and use the real Chrome browser
            browser = p.chromium.launch(
                channel="chrome", 
                headless=debug_mode["headless"],
                args=["--disable-blink-features=AutomationControlled"]
            )
            
            # Add viewport size to look like a real desktop user
            context = browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                viewport={"width": 1920, "height": 1080}
            )
            page = context.new_page()

            # Inject human-like browser fingerprints to bypass WAFs without external dependencies
            page.add_init_script("""
                Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
                window.navigator.chrome = { runtime: {} };
                Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });
                Object.defineProperty(navigator, 'languages', { get: () => ['he-IL', 'he', 'en-US', 'en'] });
                
                const originalQuery = window.navigator.permissions.query;
                window.navigator.permissions.query = (parameters) => (
                    parameters.name === 'notifications' ? 
                        Promise.resolve({ state: Notification.permission }) : 
                        originalQuery(parameters)
                );
            """)
            
            # Uses the dynamic wait mode (networkidle for SPAs, domcontentloaded for the rest)
            page.goto(jobs_url, wait_until=wait_until_mode, timeout=60000)

            # Handle popups/cookie banners if a selector is provided
            if popup_selector:
                try:
                    page.wait_for_selector(popup_selector, timeout=5000)
                    page.click(popup_selector)
                    page.wait_for_timeout(2000)
                except Exception:
                    pass # Popup didn't appear, move on smoothly

            # Generic Redirect: If the site redirected us away from the target URL, navigate back
            if not page.url.startswith(jobs_url):
                page.goto(jobs_url, wait_until=wait_until_mode, timeout=60000)
                page.wait_for_timeout(3000)
            
            # --- DYNAMIC UI FILTER CLICKS (Driven entirely by targets.json) ---
            if filter_clicks:
                for step in filter_clicks:
                    try:
                        action = step.get("action")
                        selector = step.get("selector")
                        text = step.get("text")
                        description = step.get("description", selector)

                        if text:
                            btn = page.locator(selector, has_text=text).first
                        else:
                            btn = page.locator(selector).first
                        
                        if action == "click":
                            # Standard click with text matching
                            btn.wait_for(state="visible", timeout=10000)
                            btn.click()
                            page.wait_for_timeout(1500)
                            if debug_mode["clicks"]:
                                print(f"{Colors.GREEN}DEBUG: Clicked filter '{description}.{Colors.RESET}")
                            
                        elif action == "js_click":
                            # JS click for elements hidden under animations/dropdowns
                            btn.wait_for(state="attached", timeout=5000)
                            page.evaluate("(element) => element.click()", btn.element_handle())
                            page.wait_for_timeout(2000)
                            if debug_mode["clicks"]:
                                print(f"{Colors.GREEN}DEBUG: Clicked filter '{description} with JavaScript.{Colors.RESET}")
                            
                        elif action == "click_all_suboptions":
                            # Click all items in an active sub-menu (like cities)
                            city_buttons = page.locator(selector).all()
                            if city_buttons:
                                for city_btn in city_buttons:
                                    page.evaluate("(element) => element.click()", city_btn.element_handle())
                                    if debug_mode["clicks"]:
                                        print(f"{Colors.GREEN}DEBUG: Clicked suboption for filter '{description}.{Colors.RESET}")
                                    page.wait_for_timeout(500)
                                page.wait_for_timeout(3000) # Wait for React/Vue to render
                                
                    except Exception as e:
                        print(f"Note: Filter step failed ({step.get('description', '')}): {e}")

            # Convert class name to a valid CSS selector and escape Tailwind colons (e.g., hover:text-blue -> hover\:text-blue)
            raw_classes = (job_container_class or "").split()
            css_selector = ("." + ".".join(raw_classes).replace(":", r"\:")) if raw_classes else ""
            
            if css_selector:
                # Wait explicitly for the job elements to render on the screen
                try:
                    page.wait_for_selector(css_selector, timeout=20000)
                    
                    # Pagination Loop: Click 'Next' and accumulate HTML from all pages
                    for page_num in range(1, 50): # Safety limit to prevent infinite loops
                        page.wait_for_timeout(4000) # Give React time to render the jobs
                        
                        # Accumulate this page's HTML to our mega-document
                        visible_job_locators = page.locator(css_selector).all()
                        for loc in visible_job_locators:
                            if loc.is_visible():
                                html_content += loc.evaluate("element => element.outerHTML")
                        
                        # Use custom pagination selector from JSON if provided, otherwise fallback to generic defaults
                        if pagination_selector:
                            next_btn = page.locator(pagination_selector).first
                        else:
                            next_btn = page.locator('button[aria-label*="Next" i], a[aria-label*="Next" i], button[aria-label*="הבא"], a[aria-label*="הבא"]').first
                        
                        if next_btn.is_visible():
                            # React sometimes uses 'aria-disabled'
                            is_aria_disabled = next_btn.get_attribute("aria-disabled") == "true"
                            
                            # Safely check native disabled state (will fail on <a> tags, so we use try/except)
                            is_native_disabled = False
                            try:
                                is_native_disabled = next_btn.is_disabled()
                            except Exception:
                                pass 

                            if not is_aria_disabled and not is_native_disabled:
                                # Force the click using JavaScript to bypass loaders and overlays
                                next_btn.evaluate("node => node.click()")
                            else:
                                break
                        else:
                            break
                            
                except Exception:
                    # Fallback: If wait_for_selector timed out, check if the elements are actually present in the DOM anyway
                    fallback_locators = page.locator(css_selector).all()
                    for loc in fallback_locators:
                        try:
                            if loc.is_visible():
                                html_content += loc.evaluate("element => element.outerHTML")
                        except Exception:
                            pass
                    else:
                        # Truly failed to find anything
                        print(f"\033[91mTimeout waiting for job elements for {company_name}.\033[0m")
            else:
                # When job_container_class is empty, capture the full rendered page HTML directly
                page.wait_for_timeout(4000)
                html_content = page.content()
            
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
    if css_selector:
        job_elements = soup.select(f"a{css_selector}, {css_selector} a, {css_selector}")
    else:
        link_selector = f'a[href*="{link_contains}"]' if link_contains else "a[href]"
        job_elements = [a.find_parent("tr") or a for a in soup.select(link_selector)]

    if debug_mode["jobs_html"]:
        print(f"{Colors.GREEN}DEBUG: selector={css_selector}, html_len={len(html_content)}, job_elements={len(job_elements)}{Colors.RESET}")
        if job_elements:
            print(f"{Colors.GREEN}DEBUG: First element: {job_elements[0]}{Colors.RESET}")
    
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
            title = title_element.get_text(strip=True) if title_element else ""
        else:
            title_element = job.find(class_='il-title') or job.find('h3') or job.find('h2')
            title = title_element.get_text(strip=True) if title_element else ""

        # Generic guard: If the title is empty or matches known generic UI buttons, ignore this element
        ignore_titles = ["browse positions", "apply now", "learn more", "view job", "apply"]
        if not title or title.lower() in ignore_titles:
            continue
        
        # Clean up prefixes if they exist
        if title.startswith("Learn more about "):
            title = title.replace("Learn more about ", "")
        
        # If there's no title at all, skip
        if not title:
            continue

        title_lower = title.lower()

        # --- SMART FILTERING LOGIC ---
        
        # Condition 1: Check job type using smart regex (if provided)
        has_job_type = False
        if job_types:
            for kw in job_types:
                kw_escaped = re.escape(kw.lower())
                # Prevent English words from starting mid-word, ignore Hebrew prefixes
                # Optional spaces/dashes/slashes followed by valid plural/female suffixes
                # Negative lookahead blocks trailing letters (e.g. "internal")
                pattern = r'(?<![a-z])' + kw_escaped + r'(?:[\s/-]*(?:s|ship|ships|ים|ות|ית))?(?![a-zא-ת])'
                
                if re.search(pattern, title_lower):
                    has_job_type = True
                    break
        else:
            has_job_type = True # Pass if list is empty

        # Condition 2: Check field keywords using simple substring matching (if provided)
        has_field = False
        if field_keywords:
            if any(kw.lower() in title_lower for kw in field_keywords):
                has_field = True
        else:
            has_field = True # Pass if list is empty

        # Skip the job if it doesn't meet BOTH conditions
        if job_types and field_keywords:
            if not (has_job_type and has_field):
                continue
        elif job_types and not field_keywords:
            if not has_job_type:
                continue
        elif field_keywords and not job_types:
            if not has_field:
                continue
        
        # --- END SMART FILTERING ---

        # Extract full card text to check for location validity
        card_full_text = job.get_text().lower()
        
        # Generic check driven by targets.json (no hardcoded company names)
        if required_locations:
            if not any(loc.lower() in card_full_text for loc in required_locations):
                if debug_mode["pagination"]:
                    print(f"{Colors.GREEN}DEBUG: Skipped location: {title} | {card_full_text[:180]}{Colors.RESET}")
                continue

        # Process the final link based on whether href was found or missing
        if href and not href.strip().startswith('#'):
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
            # Fallback if no href was found (or href is just '#'): attach requisition ID when available
            req_match = re.search(r'requisition\s*id\s*:\s*([a-z0-9_-]+?)(?=\s*(?:work\s*locations|schedule|job\s*posting|$))', card_full_text, re.IGNORECASE)
            if req_match:
                full_link = f"{jobs_url}#req={req_match.group(1).upper()}"
            else:
                full_link = jobs_url

        # Create a unique identifier to prevent duplicate alerts
        job_id_string = f"{company_name}_{title}_{full_link}"
        job_id = hashlib.md5(job_id_string.encode()).hexdigest()
        
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
        
    if new_jobs_found and db_collection:
        print(f"Finished scrape for {company_name}: New jobs were added to the database.")
    else:
        print(f"Finished scrape for {company_name}: No new jobs found.")