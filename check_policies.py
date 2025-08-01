#!/usr/bin/env python3
import subprocess
import sys
import signal
import os
from pathlib import Path
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor

# -----------------------------------------------------------------------------
# CONFIGURATION
# -----------------------------------------------------------------------------
TIMEOUT = 30  # seconds per policy
BASE = Path(__file__).resolve().parent
SRC_DIR = BASE.parents[1] / "src"
LOG_PATH = BASE / "check_policies.log"

# Define exactly which sub-folders to check, in order.
FOLDERS = [
    ("repaired", "original_policy"),
    ("repaired", "results"),
    ("relaxed", "original_policy"),
    ("broken", "original_policy"),
]

# -----------------------------------------------------------------------------
# STATS STORAGE
# -----------------------------------------------------------------------------
stats = {
    f"{cat}/{sub}": {"total": 0, "sat": [], "unsat": [], "errors": [], "timeouts": []}
    for cat, sub in FOLDERS
}


# -----------------------------------------------------------------------------
# INTERRUPT HANDLING
# -----------------------------------------------------------------------------
def _on_sigint(signum, frame):
    print("\nInterrupted. Summary so far:\n")
    _print_summary()
    sys.exit(1)


signal.signal(signal.SIGINT, _on_sigint)


# -----------------------------------------------------------------------------
# SUMMARY PRINTER
# -----------------------------------------------------------------------------
def _print_summary():
    for label, s in stats.items():
        print(f"{label}:")
        print(f"  Total checked: {s['total']}")
        print(f"    SAT:       {len(s['sat'])}")
        print(f"    UNSAT:     {len(s['unsat'])}")
        print(f"    Errors:    {len(s['errors'])}")
        print(f"    Timeouts:  {len(s['timeouts'])}")
        if s["unsat"]:
            print("    UNSAT files:")
            for p in s["unsat"]:
                print("      ", p.name)
        if s["errors"]:
            print("    Errored files:")
            for p in s["errors"]:
                print("      ", p.name)
        if s["timeouts"]:
            print("    Timed-out files:")
            for p in s["timeouts"]:
                print("      ", p.name)
        print()


# -----------------------------------------------------------------------------
# WORKER
# -----------------------------------------------------------------------------
def _check_policy(task):
    label, policy_path = task
    cmd = ["python3", "quacky.py", "-p1", str(policy_path), "-b", "100"]
    try:
        proc = subprocess.run(
            cmd,
            cwd=SRC_DIR,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            timeout=TIMEOUT,
        )
        return {
            "label": label,
            "policy": policy_path,
            "timeout": False,
            "returncode": proc.returncode,
            "output": proc.stdout,
        }
    except subprocess.TimeoutExpired:
        return {
            "label": label,
            "policy": policy_path,
            "timeout": True,
            "returncode": None,
            "output": None,
        }


# -----------------------------------------------------------------------------
# MAIN
# -----------------------------------------------------------------------------
def main():
    if not SRC_DIR.is_dir():
        print(f"Error: could not find src/ at {SRC_DIR}", file=sys.stderr)
        sys.exit(1)

    # Build ordered task list
    tasks = []
    for cat, sub in FOLDERS:
        policy_dir = BASE / "filtered_pages" / cat / sub
        if not policy_dir.is_dir():
            print(f"Warning: missing {policy_dir}", file=sys.stderr)
            continue
        files = sorted(policy_dir.glob("*.json"), key=lambda p: int(p.stem))
        for p in files:
            stats[f"{cat}/{sub}"]["total"] += 1
            tasks.append((f"{cat}/{sub}", p))

    # Prepare log
    with open(LOG_PATH, "w") as log_f:
        log_f.write(f"=== check_policies run at {datetime.now().isoformat()} ===\n\n")

        # Parallel execution
        workers = os.cpu_count() or 4
        with ThreadPoolExecutor(max_workers=workers) as exe:
            for result in exe.map(_check_policy, tasks):
                label = result["label"]
                policy = result["policy"]
                timeout = result["timeout"]
                code = result["returncode"]
                raw_out = result["output"]
                out = raw_out.strip() if raw_out else ""

                # Log everything
                log_f.write(f"--- [{label}] {policy.name} ---\n")
                if timeout:
                    log_f.write(f"[TIMEOUT >{TIMEOUT}s]\n\n")
                else:
                    log_f.write(out + "\n\n")

                # Terminal output only for issues
                bucket = stats[label]
                if timeout:
                    bucket["timeouts"].append(policy)
                    print(f"TIMEOUT ({label}): {policy.name}")
                elif code is None or code != 0:
                    bucket["errors"].append(policy)
                    print(f"ERROR   ({label}): {policy.name}")
                else:
                    if "satisfiability: sat" in out:
                        bucket["sat"].append(policy)
                    else:
                        bucket["unsat"].append(policy)
                        print(f"UNSAT   ({label}): {policy.name}")

        log_f.write("=== end of run ===\n")

    # Final summary
    print(f"\nDone. Detailed log written to {LOG_PATH}\n")
    _print_summary()


if __name__ == "__main__":
    main()
