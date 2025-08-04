#!/usr/bin/env python3
import subprocess, sys

# get all tracked paths
out = subprocess.check_output(["git", "ls-files"], text=True)
ads = [p for p in out.splitlines() if p.endswith(":Zone.Identifier")]

if not ads:
    print("No Zone.Identifier files to remove.")
    sys.exit(0)

# remove them
subprocess.run(["git", "rm", "-f"] + ads, check=True)
subprocess.run(["git", "commit", "-m", "Remove Zone.Identifier streams"], check=True)
subprocess.run(["git", "push"], check=True)
print(f"Removed {len(ads)} Zone.Identifier files.")
