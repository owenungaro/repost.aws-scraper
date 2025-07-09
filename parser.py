import os
from bs4 import BeautifulSoup

SAVED_DIR = "saved_pages/"

import json


def extract_post_data(soup):
    # Extract title
    title_tag = soup.find("h1")
    title = title_tag.get_text(strip=True) if title_tag else None

    # Extract post body
    main_post = None
    main_container = soup.find("main") or soup.find("div", class_="css-12dv1kw")
    if main_container:
        # Look for the post/question text block
        candidates = main_container.find_all(
            "div", class_="custom-md-style", recursive=True
        )
        if candidates:
            main_post = candidates[0]  # First is almost always the question text

    if main_post:
        question_text = main_post.get_text(separator="\n").strip()
    else:
        question_text = ""
    # Extract author
    author_tag = soup.find("a", class_="Avatar_displayNameLink__ZHYcf")
    if author_tag:
        author = author_tag.get_text(strip=True)
    else:
        aws_official_tag = soup.find("span", class_="AWSAvatar_supportLabel__9dmxA")
        author = aws_official_tag.get_text(strip=True) if aws_official_tag else None

    # Extract tags
    tag_section = soup.find("div", class_="Metadata_wrapper__2eXBk")
    tags = []
    if tag_section:
        tag_spans = tag_section.find_all("span", class_="ant-tag")
        tags = [span.get_text(strip=True) for span in tag_spans]

    # Extract datePublished
    date = None
    json_ld_tag = soup.find("script", type="application/ld+json")
    if json_ld_tag:
        try:
            json_data = json.loads(json_ld_tag.string)
            date = json_data.get("datePublished") or json_data.get(
                "mainEntity", {}
            ).get("datePublished")
        except (json.JSONDecodeError, TypeError):
            pass

    # Extract ACCEPTED status
    accepted_tag = soup.find("span", string="Accepted Answer")
    accepted = accepted_tag is not None

    return {
        "title": title,
        "author": author,
        "date": date,
        "tags": tags,
        "body": question_text,
        "accepted": accepted,
    }


def parse_all_posts():
    posts = []
    for file_name in os.listdir(SAVED_DIR):
        if file_name.endswith(".html"):
            file_path = os.path.join(SAVED_DIR, file_name)
            with open(file_path, "r", encoding="utf-8") as f:
                soup = BeautifulSoup(f, "html.parser")
                post_data = extract_post_data(soup)
                posts.append(post_data)
    return posts


if __name__ == "__main__":
    all_posts = parse_all_posts()
    print(f"Parsed {len(all_posts)} post(s)")
    for post in all_posts:
        print(f"{post['body']}")
