#!/usr/bin/env python3
"""Count your work commits per day from local git clones.

Run this on your work machine. It finds every git repo under the folders you
give it, counts commits authored by your work email(s) per day, and writes the
counts into data/work-contributions.json. Only dates and counts are saved: no
repo names, messages or code.

  python3 scripts/export_work_commits.py --email you@company.com ~/work
"""
import argparse
import json
import os
import subprocess
from datetime import date, timedelta
from pathlib import Path

WORK_FILE = Path(__file__).resolve().parent.parent / "data" / "work-contributions.json"


def find_repos(roots):
    for root in roots:
        for dirpath, dirnames, _ in os.walk(os.path.expanduser(root)):
            if ".git" in dirnames or os.path.isfile(os.path.join(dirpath, ".git")):
                yield dirpath
                dirnames[:] = []  # don't descend into the repo
            else:
                dirnames[:] = [d for d in dirnames if not d.startswith(".") and d != "node_modules"]


def commit_dates(repo, emails, since):
    cmd = ["git", "-C", repo, "log", "--all", f"--since={since}", "--format=%H %ad", "--date=short"]
    cmd += [f"--author={e}" for e in emails]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        return []
    return [line.split() for line in result.stdout.splitlines() if line.strip()]


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("folders", nargs="+", help="folders containing your work repos")
    parser.add_argument("--email", action="append", required=True, help="your work commit email (repeatable)")
    parser.add_argument("--since", default=(date.today() - timedelta(days=371)).isoformat(),
                        help="start date, YYYY-MM-DD (default: about a year ago)")
    args = parser.parse_args()

    seen = {}  # commit hash -> date, so the same commit in two clones counts once
    repos = list(find_repos(args.folders))
    for repo in repos:
        for sha, day in commit_dates(repo, args.email, args.since):
            seen[sha] = day

    counts = {}
    for day in seen.values():
        counts[day] = counts.get(day, 0) + 1

    existing = json.loads(WORK_FILE.read_text()) if WORK_FILE.exists() else {}
    # Scanned range replaces what was there; older entries are kept.
    merged = {d: n for d, n in existing.items() if d < args.since}
    merged.update(counts)
    WORK_FILE.parent.mkdir(parents=True, exist_ok=True)
    WORK_FILE.write_text(json.dumps(dict(sorted(merged.items())), indent=2) + "\n")

    print(f"Scanned {len(repos)} repos, found {len(seen)} commits on {len(counts)} days since {args.since}")
    print(f"Updated {WORK_FILE}")


if __name__ == "__main__":
    main()
