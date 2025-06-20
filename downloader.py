from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup
import os
import time
import random
from urllib.parse import urlparse
from concurrent.futures import ThreadPoolExecutor, as_completed

SAVED_DIR = "saved_pages/"
os.makedirs(SAVED_DIR, exist_ok=True)

def url_to_filename(url):
    parsed = urlparse(url)
    path = parsed.path.strip("/").replace("/", "_")
    return path or "index"


def generate_filename(url):
    parsed = urlparse(url)
    path = parsed.path.strip("/").replace("/", "_")
    return os.path.join(SAVED_DIR, f"{path}.html")

def save_page(url, name="", verbose = False):
    if not name:
        name = url.split("/")[-1] or "index"

    path = os.path.join(SAVED_DIR, f"{name}.html")
    if os.path.exists(path):
        if verbose:
            print(f"[=] Skipping (already saved): {url}")
        return

    with sync_playwright() as p:
        # Launch browser in headless mode with realistic user using context
        # AWS blocks "bot" and "scraping" user attempts
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(user_agent=(
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/114.0.0.0 Safari/537.36"
        ))

        # Creates a new page and injects headers
        page = context.new_page()
        page.set_extra_http_headers({
            "Accept-Language": "en-US,en;q=0.9",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
        })

        # Visits URL and waits for JS to finish loading
        # AWS populates forum posts using JS and not HTML (standard)
        if verbose:    
            print(f"[>] Saving: {url}")
        page.goto(url, timeout=60000)
        page.wait_for_load_state("networkidle")

        # Gets rendered HTML and writes to disk
        content = page.content()
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        browser.close()

def save_page_safe(url, verbose = False):
    try:
        time.sleep(random.uniform(1.0, 2.0))  # Random delay
        save_page(url, verbose = verbose)
    except Exception as e:
        if verbose:
            print(f"[!] Error saving {url}: {e}")

def scrape_page(url, verbose = False):
    save_page(url, name="index", verbose = verbose)
    with open(os.path.join(SAVED_DIR, "index.html"), "r", encoding="utf-8") as f:
        soup = BeautifulSoup(f, "html.parser")

    valid_links = []

    # Looks for post links in <a> tags
    for a in soup.find_all("a", href=True):
        classes = a.get("class", [])
        if any(c.startswith(("QuestionCard", "ArticleCard", "KCArticleCard")) for c in classes): # Add to this list for all specific HTML tags
            href = a["href"]
            if href.startswith("/"):
                full_url = "https://repost.aws" + href
                valid_links.append(full_url)
                if verbose:
                    print(f"[+] Found post link: {full_url}")
    
    # Finds next page link
    next_button = soup.find("a", {"aria-label": "Go to next page"})
    if next_button and next_button.get("href"):
        next_href = next_button["href"]
        next_url = "https://repost.aws" + next_href
        print(f"[NEXT] {next_url}")
    else:
        print("[NEXT] No next page found.")

    return valid_links, next_url

def iterate_pages(verbose = False):
    """
    Returns:
        tuple: (number of pages visited, list of unique post links)
    """

    base_url = "https://repost.aws/search/content?globalSearch=IAM+Policy&sort=recent&page=eyJ2IjoyLCJuIjoiOHlUcTNKbG1CVmJZbkdlemZiRWx1dz09IiwidCI6ImVTZUlIRkxoUFo0ejc5OGVDM1dockE9PSJ9"
    page = 1
    all_links = []

    next_url = base_url
    while next_url:
        if verbose:
            print(f"[Downloader] Scraping page {page}: {next_url}")
        links, next_url = scrape_page(next_url, verbose = verbose)
        all_links.extend(links)
        page += 1
        #TODO Pagination

    unique_links = list(set(all_links)) # Unique post URLS

    # Logic moved to scrape.py
    # # Multithread download
    # with ThreadPoolExecutor(max_workers = 4) as executor:
    #     futures = [executor.submit(save_page_safe, url) for url in unique_links]
    #     for future in as_completed(futures):
    #         future.result() # Block until all downloads complete (C++ wait())

    return page - 1, unique_links

if __name__ == "__main__":
    pages, links = iterate_pages()
    print(f"Scraped {pages} page(s), found {len(links)} post links.")
