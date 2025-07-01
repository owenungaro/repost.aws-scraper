import os
import json
import shutil
import time
import re


def contains_statement(text):
    return '"Statement"' in text or '"Statement"' in text.replace(" ", "")


def extract_first_policy_block(text):
    depth = 0
    start_idx = None
    for i, c in enumerate(text):
        if c == '{':
            if depth == 0:
                start_idx = i
            depth += 1
        elif c == '}':
            depth -= 1
            if depth == 0 and start_idx is not None:
                block = text[start_idx:i + 1]
                try:
                    data = json.loads(block)
                    if "Version" in data and "Statement" in data:
                        before = text[:start_idx]
                        after = text[i + 1:]
                        remaining = (before + after).strip()
                        return data, remaining
                except Exception:
                    continue
    return None, text



def load_json(filepath):
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"[!] Failed to load {filepath}: {e}")
        return {}


def filter_and_save(saved_dir='saved_pages', filtered_dir='filtered_pages'):
    os.makedirs(os.path.join(filtered_dir, 'original_policy'), exist_ok=True)
    os.makedirs(os.path.join(filtered_dir, 'request'), exist_ok=True)
    os.makedirs(os.path.join(filtered_dir, 'results'), exist_ok=True)

    index = 0

    for folder in os.listdir(saved_dir):
        folder_path = os.path.join(saved_dir, folder)
        if not os.path.isdir(folder_path):
            continue

        body_path = os.path.join(folder_path, 'body.json')
        ans_path = os.path.join(folder_path, 'accepted_answer.json')
        if not (os.path.exists(body_path) and os.path.exists(ans_path)):
            continue

        body_json = load_json(body_path)
        ans_json = load_json(ans_path)

        body_text = body_json.get('body', '')
        ans_text = ans_json.get('accepted_answer', '')

        if contains_statement(body_text) and contains_statement(ans_text):
            body_policy, body_remainder = extract_first_policy_block(body_text)
            ans_policy, _ = extract_first_policy_block(ans_text)

            if body_policy and ans_policy:
                with open(os.path.join(filtered_dir, 'original_policy', f"{index}.json"), 'w') as f:
                    json.dump(body_policy, f, indent=2)

                with open(os.path.join(filtered_dir, 'request', f"{index}.json"), 'w') as f:
                    json.dump({"body": body_remainder}, f, indent=2)

                with open(os.path.join(filtered_dir, 'results', f"{index}.json"), 'w') as f:
                    json.dump(ans_policy, f, indent=2)

                print(f"[+] Saved triplet #{index}")
                index += 1

    print(f"[INFO] Total matched posts: {index}")


if __name__ == "__main__":
    start = time.time()
    print("[INFO] Running updated filter...")
    filter_and_save()
    print(f"[INFO] Done in {time.time() - start:.2f}s")
