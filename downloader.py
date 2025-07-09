# Test1: 540 in 54 minutes
# Test2: 300 in 9 minutes
# Test3: 3454 in 408 minutes
# Test4: in 9968 289 seconds (17376.05 seconds)


# TODO:
# Fix flags (download and structure don't work)

from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup
import os
import time
import random
from urllib.parse import urlparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from playwright.sync_api import sync_playwright

SAVED_DIR = "saved_pages/"
os.makedirs(SAVED_DIR, exist_ok=True)


# Convert URL to safe filename
def url_to_filename(url):
    parsed = urlparse(url)
    path = parsed.path.strip("/").replace("/", "_")
    return path or "index"


# Generate path from URL
def generate_filename(url):
    parsed = urlparse(url)
    path = parsed.path.strip("/").replace("/", "_")
    return os.path.join(SAVED_DIR, f"{path}.html")


def save_page(url, context, name="", verbose=False, proxy=None):
    if not name:
        name = url.split("/")[-1] or "index"

    path = os.path.join(SAVED_DIR, f"{name}.html")
    if os.path.exists(path):
        if verbose:
            print(f"[=] Skipping (already saved): {url}")
        return True

    # Creates a new page from shared browser context
    page = context.new_page()

    # Stealth anti bot patches
    page.add_init_script(
        """
        Object.defineProperty(navigator, 'webdriver', { get: () => false });
        Object.defineProperty(navigator, 'platform', { get: () => 'Win32' });
        window.chrome = { runtime: {} };
        Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3] });
        Object.defineProperty(navigator, 'languages', { get: () => ['en-US', 'en'] });
    """
    )

    if verbose:
        print(f"[>] Saving: {url}")

    # Attempts to load page
    try:
        page.goto(url, timeout=60000)
    except Exception as e:
        print(f"[!] Failed to load page {url}: {e}")
        return False

    # Checks for CAPTCHA
    content = page.content()
    if (
        "JavaScript is disabled" in content
        or "verify that you're not a robot" in content
    ):
        if verbose:
            print(f"[!] CAPTCHA detected on: {url}")
        try:
            # Waits for user to solve CAPTCHA (indefinitely)
            page.wait_for_selector(".custom-md-style", timeout=0)
        except:
            print("[!] Manual CAPTCHA solve timeout.")

    # Waits for page to load context
    try:
        page.wait_for_selector(".custom-md-style", timeout=15000)
    except:
        if verbose:
            print("[!] Warning: content selector `.custom-md-style` not found.")

    # Save HTML content
    content = page.content()
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)

    page.close()
    return True


def save_page_safe(url, context, verbose=False):
    try:
        time.sleep(random.uniform(0.3, 0.7))  # Random delay, prevents bot detection
        save_page(url, context, verbose=verbose)
    except Exception as e:
        if verbose:
            print(f"[!] Error saving {url}: {e}")


def scrape_page(url, context, verbose=False):
    next_url = None  # Default value if nothing is found

    # Downloads search page results
    success = save_page(url, context, name="index", verbose=verbose)
    if not success:
        if verbose:
            print(f"[!] Skipping parse of {url} due to failed save.")
        return [], None

    # Loads saved HTML
    with open(os.path.join(SAVED_DIR, "index.html"), "r", encoding="utf-8") as f:

        soup = BeautifulSoup(f, "html.parser")

    valid_links = []

    # Extracts useful info
    for a in soup.find_all("a", href=True):
        classes = a.get("class", [])
        if any(
            c.startswith(("QuestionCard", "ArticleCard", "KCArticleCard"))
            for c in classes
        ):
            href = a["href"]
            if href.startswith("/"):
                full_url = "https://repost.aws" + href
                valid_links.append(full_url)
                if verbose:
                    print(f"[+] Found post link: {full_url}")

    # Check if there is a next page button
    next_button = soup.find("a", {"aria-label": "Go to next page"})
    if next_button and next_button.get("href"):
        next_href = next_button["href"]
        next_url = "https://repost.aws" + next_href
        if verbose:
            print(f"[NEXT] {next_url}")
    else:
        if verbose:
            print("[NEXT] No next page found.")

    return valid_links, next_url


def iterate_pages(verbose=False):
    """
    Returns:
        tuple: (number of pages visited, list of unique post links)
    """

    base_url = "https://repost.aws/search/content?globalSearch=IAM+Policy&sort=recent"
    page = 1
    all_links = []

    next_url = base_url
    while next_url:
        if verbose:
            print(f"[Downloader] Scraping page {page}: {next_url}")
        links, next_url = scrape_page(next_url, verbose=verbose)
        all_links.extend(links)
        page += 1
        # TODO Pagination

    unique_links = list(set(all_links))  # Unique post URLS

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
