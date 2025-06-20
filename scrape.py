import os
import json
import argparse
from bs4 import BeautifulSoup
from parser import extract_post_data
from downloader import scrape_page, save_page_safe, SAVED_DIR
from concurrent.futures import ThreadPoolExecutor, as_completed
import time

def sanitize_name(filename):
    return filename.replace(".html", "").replace("/", "_")

def save_post_files(file_path, verbose=False):
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
            "tags": data["tags"]
        }, f, indent=2)

    with open(os.path.join(post_dir, "body.json"), "w", encoding="utf-8") as f:
        json.dump({"body": data["body"]}, f, indent=2)

    os.remove(file_path)

def run_one_page(url, verbose, max_links=None):
    links, next_url = scrape_page(url, verbose=verbose)

    if max_links is not None:
        links = links[:max_links]
        if verbose:
            print(f"[!] Truncating to first {max_links} links")

    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = [executor.submit(save_page_safe, link, verbose) for link in links]
        for future in as_completed(futures):
            future.result()

    html_files = [f for f in os.listdir(SAVED_DIR) if f.endswith(".html")]
    for file_name in html_files:
        save_post_files(os.path.join(SAVED_DIR, file_name), verbose=verbose)

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

    base_url = "https://repost.aws/search/content?globalSearch=IAM+Policy&sort=recent&page=eyJ2IjoyLCJuIjoiOHlUcTNKbG1CVmJZbkdlemZiRWx1dz09IiwidCI6ImVTZUlIRkxoUFo0ejc5OGVDM1dockE9PSJ9"
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
