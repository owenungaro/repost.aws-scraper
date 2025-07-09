import os
import json
import time
import argparse
import sys
import re


# Prints and overwrites terminal line (used for progress)
def print_status(message):
    sys.stdout.write("\r\033[K" + message)
    sys.stdout.flush()


# Attempts to extract the first valid IAM policy block (JSON) from text
def extract_first_policy_block(text):
    depth = 0
    start_idx = None
    for i, c in enumerate(text):
        if c == "{":
            if depth == 0:
                start_idx = i
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0 and start_idx is not None:
                block = text[start_idx : i + 1]
                try:
                    data = json.loads(block)
                    # Matches IAM style policy of Effect + Action
                    if isinstance(data, dict) and "Effect" in data and "Action" in data:
                        before = text[:start_idx]
                        after = text[i + 1 :]
                        remaining = (before + after).strip()
                        return data, remaining
                    # Matches policy with Statement
                    if isinstance(data, dict) and "Statement" in data:
                        stmts = data["Statement"]
                        if isinstance(stmts, dict):
                            stmts = [stmts]
                        if isinstance(stmts, list) and len(stmts) > 0:
                            stmt = stmts[0]
                            if (
                                isinstance(stmt, dict)
                                and "Effect" in stmt
                                and "Action" in stmt
                            ):
                                before = text[:start_idx]
                                after = text[i + 1 :]
                                remaining = (before + after).strip()
                                return data, remaining
                except Exception:
                    continue
    return None, text


# Lodas a JSON file and handles errors
def load_json(filepath):
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"[!] Failed to load {filepath}: {e}")
        return {}


# Filters posts that have a valid policy and accepted answer (repaired)
def filter_repaired(saved_dir="saved_pages", filtered_dir="filtered_pages/repaired"):
    os.makedirs(os.path.join(filtered_dir, "original_policy"), exist_ok=True)
    os.makedirs(os.path.join(filtered_dir, "intent"), exist_ok=True)
    os.makedirs(os.path.join(filtered_dir, "results"), exist_ok=True)

    index = 0
    for folder in os.listdir(saved_dir):
        folder_path = os.path.join(saved_dir, folder)
        if not os.path.isdir(folder_path):
            continue

        body_path = os.path.join(folder_path, "body.json")
        ans_path = os.path.join(folder_path, "accepted_answer.json")
        if not (os.path.exists(body_path) and os.path.exists(ans_path)):
            continue

        body_json = load_json(body_path)
        ans_json = load_json(ans_path)

        body_text = body_json.get("body", "")
        ans_text = ans_json.get("accepted_answer", "")

        body_policy, body_remainder = extract_first_policy_block(body_text)
        ans_policy, _ = extract_first_policy_block(ans_text)

        if body_policy and ans_policy:
            # Saves triplet: original, intent, result
            with open(
                os.path.join(filtered_dir, "original_policy", f"{index}.json"), "w"
            ) as f:
                json.dump(body_policy, f, indent=2)

            with open(
                os.path.join(filtered_dir, "intent", f"{index}.json"),
                "w",
                encoding="utf-8",
            ) as f:
                f.write(body_remainder.strip())

            with open(os.path.join(filtered_dir, "results", f"{index}.json"), "w") as f:
                json.dump(ans_policy, f, indent=2)

            print_status(f"[+] Saved repaired triplet #{index}")
            index += 1

    print(f"\n[INFO] Total repaired posts: {index}")


# Filteres posts that have a valid policy but no accepted answer (broken)
def filter_broken(saved_dir="saved_pages", filtered_dir="filtered_pages/broken"):
    os.makedirs(os.path.join(filtered_dir, "original_policy"), exist_ok=True)
    os.makedirs(os.path.join(filtered_dir, "intent"), exist_ok=True)

    index = 0
    for folder in os.listdir(saved_dir):
        folder_path = os.path.join(saved_dir, folder)
        if not os.path.isdir(folder_path):
            continue

        body_path = os.path.join(folder_path, "body.json")
        ans_path = os.path.join(folder_path, "accepted_answer.json")
        if not os.path.exists(body_path) or os.path.exists(ans_path):
            continue

        body_json = load_json(body_path)
        body_text = body_json.get("body", "")
        body_policy, body_remainder = extract_first_policy_block(body_text)

        if body_policy:
            with open(
                os.path.join(filtered_dir, "original_policy", f"{index}.json"), "w"
            ) as f:
                json.dump(body_policy, f, indent=2)

            with open(
                os.path.join(filtered_dir, "intent", f"{index}.json"),
                "w",
                encoding="utf-8",
            ) as f:
                f.write(body_remainder.strip())

            print_status(f"[+] Saved broken pair #{index}")
            index += 1

    print(f"\n[INFO] Total broken posts: {index}")


# Loose regex detection of potential IAM policy
def relaxed_policy_search(text):
    if isinstance(text, dict):
        text = json.dumps(text)
    text = text.lower()
    return bool(
        re.search(r'"?effect"?\s*:\s*"?allow"?', text)
        and re.search(r'"?action"?\s*:\s*["{\[]', text)
    )


# Filteres "relaxed" posts: no accepted answer, and loosely detected policy (no overlap with broken)
def filter_relaxed(
    saved_dir="saved_pages",
    filtered_dir="filtered_pages/relaxed",
    broken_dir="filtered_pages/broken",
):
    # Checks for broken folder to avoid overlapping
    if not os.path.exists(os.path.join(broken_dir, "original_policy")):
        print(
            "[ERROR] Broken folder not found. Please run with -b first to ensure relaxed results are unique."
        )
        return

    os.makedirs(os.path.join(filtered_dir, "original_policy"), exist_ok=True)
    os.makedirs(os.path.join(filtered_dir, "intent"), exist_ok=True)

    # Index blacklist from broken results
    broken_folders = set()
    broken_base = os.path.join(broken_dir, "original_policy")
    if os.path.exists(broken_base):
        for fname in os.listdir(broken_base):
            try:
                idx = int(fname.replace(".json", ""))
                broken_folders.add(idx)
            except:
                continue

    index = 0
    global_index = 0  # Keeps track of order of scanned folders
    for folder in os.listdir(saved_dir):
        folder_path = os.path.join(saved_dir, folder)
        if not os.path.isdir(folder_path):
            continue

        body_path = os.path.join(folder_path, "body.json")
        ans_path = os.path.join(folder_path, "accepted_answer.json")

        # Skips postswith accepted answers or if used in broken
        if os.path.exists(ans_path):
            continue
        if global_index in broken_folders:
            global_index += 1
            continue

        body_json = load_json(body_path)
        body_text = body_json.get("body", "")
        if not relaxed_policy_search(body_text):
            global_index += 1
            continue

        body_policy, body_remainder = extract_first_policy_block(body_text)

        if body_policy:
            with open(
                os.path.join(filtered_dir, "original_policy", f"{index}.json"), "w"
            ) as f:
                json.dump(body_policy, f, indent=2)

            with open(
                os.path.join(filtered_dir, "intent", f"{index}.json"),
                "w",
                encoding="utf-8",
            ) as f:
                f.write(body_remainder.strip())

            print_status(f"[+] Saved relaxed pair #{index}")
            index += 1

        global_index += 1

    print(f"\n[INFO] Total relaxed posts: {index}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Filter IAM policy forum posts")
    parser.add_argument(
        "-r",
        "--repaired",
        action="store_true",
        help="Extract only posts with accepted answers (repaired)",
    )
    parser.add_argument(
        "-b",
        "--broken",
        action="store_true",
        help="Extract only posts with no accepted answer (broken)",
    )
    parser.add_argument(
        "-x",
        "--relaxed",
        action="store_true",
        help="Extra-loose regex-based filtering for weak policies",
    )
    parser.add_argument("-s", "--single", help="Test a specific folder")

    args = parser.parse_args()
    start = time.time()
    ran = False

    if args.single:
        folder_path = os.path.join("saved_pages", args.single)
        if not os.path.isdir(folder_path):
            print(f"[!] Folder '{args.single}' not found.")
        else:
            body_path = os.path.join(folder_path, "body.json")
            ans_path = os.path.join(folder_path, "accepted_answer.json")
            has_body = os.path.exists(body_path)
            has_ans = os.path.exists(ans_path)
            print(f"[INFO] Testing folder '{args.single}'...")
            if not has_body:
                print(f"[X] Missing body.json")
            elif not has_ans:
                print(f"[>] Broken: has body.json, no accepted_answer.json")
            else:
                body_json = load_json(body_path)
                ans_json = load_json(ans_path)
                body_text = body_json.get("body", "")
                ans_text = ans_json.get("accepted_answer", "")
                bp, _ = extract_first_policy_block(body_text)
                ap, _ = extract_first_policy_block(ans_text)
                if bp and ap:
                    print(f"[>] Repaired: valid policy + accepted answer")
                else:
                    print(f"[X] Invalid or missing policy/answer")
        ran = True

    if args.repaired:
        print("[INFO] Running filter for repaired posts...")
        filter_repaired()
        ran = True

    if args.broken:
        print("[INFO] Running filter for broken posts...")
        filter_broken()
        ran = True

    if args.relaxed:
        print("[INFO] Running relaxed regex-based filter...")
        filter_relaxed()
        ran = True

    if not ran:
        parser.print_help()

    print(f"[INFO] Done in {time.time() - start:.2f}s")
