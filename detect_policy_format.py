#!/usr/bin/env python3
import os
import json
import sys
import argparse
import shutil
from typing import Any, List, Set

FOLDER_PATH = "filtered_pages"
QUARANTINE_ROOT = "quarantined_pages"


# Detect issues based on flags
def detect_policy_issues(
    path: str,
    check_sid: bool,
    check_ra: bool,
    check_empty_cond: bool,
    check_stmt: bool,
    limited: bool,
) -> List[str]:
    issues: List[str] = []
    try:
        raw = open(path, "r", encoding="utf-8").read()
    except Exception as e:
        if not limited:
            issues.append(f"File read error: {e}")
        return issues

    if not raw.strip():
        if not limited:
            issues.append("File is empty or whitespace only")
        return issues

    try:
        policy = json.loads(raw)
    except json.JSONDecodeError as e:
        if not limited:
            issues.append(f"Invalid JSON: {e.msg}")
        return issues

    stmts = policy.get("Statement")
    if stmts is None:
        if check_stmt:
            issues.append("Missing top-level 'Statement'")
        return issues

    if not isinstance(stmts, list):
        stmts = [stmts]

    for idx, stmt in enumerate(stmts):
        if not isinstance(stmt, dict):
            if not limited:
                issues.append(f"Statement[{idx}] is not an object")
            continue

        if check_ra:
            for key in ("Effect", "Action", "Resource"):
                if key not in stmt:
                    issues.append(f"Statement[{idx}] missing '{key}'")

        if check_sid and "Sid" not in stmt:
            issues.append(f"Statement[{idx}] missing 'Sid'")

        if check_empty_cond and stmt.get("Condition") == {}:
            issues.append(f"Statement[{idx}] has empty 'Condition'")

    return issues


# Repair based on flags
def repair_policy(
    path: str, repair_sid: bool, repair_stmt: bool, repair_empty_cond: bool
) -> bool:
    modified = False
    try:
        raw = open(path, "r", encoding="utf-8").read()
        policy = json.loads(raw)
    except Exception:
        return False

    if repair_stmt:
        if "Statement" not in policy:
            policy["Statement"] = []
            modified = True
        elif not isinstance(policy["Statement"], list):
            policy["Statement"] = [policy["Statement"]]
            modified = True

    if "Statement" in policy:
        stmts = policy["Statement"]
        stmts_list = stmts if isinstance(stmts, list) else [stmts]
        sid_counter = 0
        for stmt in stmts_list:
            if isinstance(stmt, dict):
                if repair_empty_cond and stmt.get("Condition") == {}:
                    del stmt["Condition"]
                    modified = True
                if repair_sid and "Sid" not in stmt:
                    sid_counter += 1
                    stmt["Sid"] = f"policy_{sid_counter}"
                    modified = True

    if modified:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(policy, f, indent=2)
    return modified


# Quarantine files missing Resource/Action/Effect
def quarantine_files(path: str):
    rel = os.path.relpath(path, FOLDER_PATH)
    dest = os.path.join(QUARANTINE_ROOT, rel)
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    shutil.copy2(path, dest)
    os.remove(path)

    parts = rel.split(os.sep)
    if len(parts) >= 3:
        top, sub, fname = parts[0], parts[1], parts[2]
        sibling = None
        if sub == "original_policy":
            sibling = os.path.join(FOLDER_PATH, top, "intent", fname)
        elif sub == "intent":
            sibling = os.path.join(FOLDER_PATH, top, "original_policy", fname)
        elif top == "repaired" and sub == "results":
            sibling = os.path.join(FOLDER_PATH, top, "original_policy", fname)

        if sibling and os.path.exists(sibling):
            dest_sib = os.path.join(
                QUARANTINE_ROOT, os.path.relpath(sibling, FOLDER_PATH)
            )
            os.makedirs(os.path.dirname(dest_sib), exist_ok=True)
            shutil.copy2(sibling, dest_sib)
            os.remove(sibling)


# Main entrypoint
def main():
    parser = argparse.ArgumentParser(
        description="Detect, repair, and quarantine AWS IAM policy JSON files under filtered_pages."
    )
    parser.add_argument(
        "-d",
        "--detect",
        help="Comma-separated list of checks: all, SID, R, condition, statement",
    )
    parser.add_argument(
        "-r",
        "--repair",
        help="Comma-separated list of repair actions: all, SID, statement, condition, quarantine",
    )
    args = parser.parse_args()

    if len(sys.argv) == 1:
        parser.print_help()
        sys.exit(0)

    detect_sel: Set[str] = (
        {s.strip().lower() for s in args.detect.split(",")} if args.detect else set()
    )
    repair_sel: Set[str] = (
        {s.strip().lower() for s in args.repair.split(",")} if args.repair else set()
    )

    check_all_d = "all" in detect_sel
    check_sid_d = check_all_d or "sid" in detect_sel
    check_ra_d = check_all_d or "r" in detect_sel
    check_empty_cond = check_all_d or "condition" in detect_sel
    check_stmt_d = check_all_d or "statement" in detect_sel
    limited_d = bool(detect_sel) and not check_all_d

    repair_all = "all" in repair_sel
    repair_sid = repair_all or "sid" in repair_sel
    repair_stmt = repair_all or "statement" in repair_sel
    repair_empty_cond = repair_all or "condition" in repair_sel
    quarantine_r = repair_all or "quarantine" in repair_sel or "r" in repair_sel

    detect_count = repair_count = quarantine_count = 0

    for root, dirs, files in os.walk(FOLDER_PATH):
        # exclude 'intent' dirs
        dirs[:] = [d for d in dirs if d.lower() != "intent"]
        dirs.sort()
        for fname in sorted(files):
            if not fname.lower().endswith(".json"):
                continue
            path = os.path.join(root, fname)

            if detect_sel:
                issues = detect_policy_issues(
                    path,
                    check_sid_d,
                    check_ra_d,
                    check_empty_cond,
                    check_stmt_d,
                    limited_d,
                )
                if issues:
                    detect_count += 1
                    print(f"{path}:")
                    for issue in issues:
                        print(f"  - {issue}")
                    print()

            if repair_sel and repair_policy(
                path, repair_sid, repair_stmt, repair_empty_cond
            ):
                repair_count += 1

            if quarantine_r:
                issues_q = detect_policy_issues(path, False, True, False, False, False)
                if any(
                    "missing 'Effect'" in i
                    or "missing 'Action'" in i
                    or "missing 'Resource'" in i
                    for i in issues_q
                ):
                    quarantine_files(path)
                    quarantine_count += 1

    if detect_sel:
        print(f"Total policies flagged: {detect_count}")
    if repair_sel:
        print(f"Total policies repaired: {repair_count}")
    if quarantine_r:
        print(f"Total policies quarantined: {quarantine_count}")


if __name__ == "__main__":
    main()
