import os
import json
import argparse
from bs4 import BeautifulSoup
from parser import extract_post_data
from downloader import scrape_page, save_page_safe, SAVED_DIR
from concurrent.futures import ThreadPoolExecutor, as_completed
from playwright.sync_api import sync_playwright
import time

def sanitize_name(filename):
    return filename.replace(".html", "").replace("/", "_")

def save_post_files(file_path, link=None, verbose=False):
    file_name = os.path.basename(file_path)
    post_name = sanitize_name(file_name)
    post_dir = os.path.join(SAVED_DIR, post_name)
    os.makedirs(post_dir, exist_ok=True)

    if verbose:
        print(f"[~] Structuring: {file_name}")

    with open(file_path, "r", encoding="utf-8") as f:
        html = f.read()
        soup = BeautifulSoup(html, "html.parser")

    with open(os.path.join(post_dir, "page.html"), "w", encoding="utf-8") as f:
        f.write(html)

    data = extract_post_data(soup)

    with open(os.path.join(post_dir, "metadata.json"), "w", encoding="utf-8") as f:
        json.dump({
            "title": data["title"],
            "author": data["author"],
            "date": data["date"],
            "tags": data["tags"],
            "accepted": data["accepted"],
            "link": link
        }, f, indent=2)

    with open(os.path.join(post_dir, "body.json"), "w", encoding="utf-8") as f:
        json.dump({"body": data["body"]}, f, indent=2)

    os.remove(file_path)

def run_one_page(url, verbose, max_links=None):
    

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                       "AppleWebKit/537.36 (KHTML, like Gecko) "
                       "Chrome/114.0.0.0 Safari/537.36",
            locale="en-US",
            timezone_id="America/New_York",
            viewport={"width": 1920, "height": 1080}
        )

        # Now that context exists, we can pass it to scrape_page
        links, next_url = scrape_page(url, context, verbose=verbose)

        if max_links is not None:
            links = links[:max_links]
            if verbose:
                print(f"[!] Truncating to first {max_links} links")

        for link in links:
            save_page_safe(link, context, verbose)

        browser.close()

    html_files = [f for f in os.listdir(SAVED_DIR) if f.endswith(".html")]
    for file_name in html_files:
        # match the file to the original link by filename
        matching_link = next((link for link in links if file_name in link or file_name.startswith(link.split("/")[-1])), None)
        save_post_files(os.path.join(SAVED_DIR, file_name), link=matching_link, verbose=verbose)


    return next_url, len(links)



def main():
    parser = argparse.ArgumentParser(description="Scrape and structure AWS re:Post pages.")
    parser.add_argument("-d", "--download", action="store_true", help="Download forum posts only")
    parser.add_argument("-s", "--structure", action="store_true", help="Structure saved HTML files and purge")
    parser.add_argument("-m", "--max", type=int, help="Max number of posts to download")
    parser.add_argument("-l", "--log", action="store_true", help="Enable verbose logging")
    args = parser.parse_args()

    verbose = args.log
    max_total = args.max
    remaining = args.max

    base_url = "https://repost.aws/search/content?globalSearch=IAM+Policy&sort=recent"
    current_url = base_url

    while current_url:
        this_page_limit = min(remaining, 30) if remaining is not None else None
        current_url, downloaded = run_one_page(current_url, verbose=verbose, max_links=this_page_limit)

        if remaining is not None:
            remaining -= downloaded
            if remaining <= 0:
                break

if __name__ == "__main__":
    start_time = time.time()
    main()
    end_time = time.time()
    print(f"Finished in {end_time - start_time:.2f} seconds.")
