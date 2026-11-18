#!/usr/bin/env python3
"""Build combined-graph.svg: personal GitHub contributions + work contributions.

Env:
  GH_TOKEN        token for the GitHub GraphQL API (the Action's own token works)
  PERSONAL_LOGIN  personal GitHub username
  WORK_LOGIN      optional work username; its public calendar is merged with
                  data/work-contributions.json, taking the larger count per day
"""
import json
import os
import sys
import urllib.request
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WORK_FILE = ROOT / "data" / "work-contributions.json"
OUT_FILE = ROOT / "combined-graph.svg"

QUERY = """
query($login: String!) {
  user(login: $login) {
    contributionsCollection {
      contributionCalendar {
        weeks { contributionDays { date contributionCount } }
      }
    }
  }
}
"""

CELL, GAP = 10, 3
STEP = CELL + GAP
LEFT, TOP = 30, 36
MONTHS = "Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split()

STYLE = """
text{font:9px -apple-system,BlinkMacSystemFont,"Segoe UI",Helvetica,Arial,sans-serif;fill:#59636e}
.h{font-size:11px;fill:#1f2328}
.l0{fill:#eff2f5}.l1{fill:#aceebb}.l2{fill:#4ac26b}.l3{fill:#2da44e}.l4{fill:#116329}
@media (prefers-color-scheme:dark){
text{fill:#9198a1}.h{fill:#f0f6fc}
.l0{fill:#151b23}.l1{fill:#033a16}.l2{fill:#196c2e}.l3{fill:#2ea043}.l4{fill:#56d364}
}
"""


def fetch_calendar(login, token):
    body = json.dumps({"query": QUERY, "variables": {"login": login}}).encode()
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=body,
        headers={
            "Authorization": f"bearer {token}",
            "Content-Type": "application/json",
            "User-Agent": "combined-contribution-graph",
        },
    )
    with urllib.request.urlopen(req) as resp:
        payload = json.load(resp)
    if payload.get("errors") or not (payload.get("data") or {}).get("user"):
        sys.exit(f"GitHub API error for {login}: {payload.get('errors')}")
    weeks = payload["data"]["user"]["contributionsCollection"]["contributionCalendar"]["weeks"]
    return {d["date"]: d["contributionCount"] for w in weeks for d in w["contributionDays"]}


def load_work_file():
    if not WORK_FILE.exists():
        return {}
    return {k: int(v) for k, v in json.loads(WORK_FILE.read_text()).items()}


def level(count, max_count):
    if count == 0:
        return 0
    # Quarters of the busiest day, like GitHub's own scale.
    return min(4, 1 + int(4 * (count - 1) / max_count))


def render(counts, end):
    start = end - timedelta(days=364)
    start -= timedelta(days=(start.weekday() + 1) % 7)  # back to Sunday
    n_weeks = (end - start).days // 7 + 1

    days = [start + timedelta(days=i) for i in range((end - start).days + 1)]
    values = {d: counts.get(d.isoformat(), 0) for d in days}
    total = sum(values.values())
    max_count = max(values.values()) or 1

    width = LEFT + n_weeks * STEP + 4
    height = TOP + 7 * STEP + 26
    out = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}" role="img" '
        f'aria-label="{total} contributions in the last year">',
        f"<style>{STYLE}</style>",
        f'<text class="h" x="{LEFT}" y="13">{total:,} contributions in the last year (personal + work)</text>',
    ]

    last_label_week = -3
    prev_month = None
    for w in range(n_weeks):
        first = start + timedelta(weeks=w)
        if first.month != prev_month and w - last_label_week >= 3:
            out.append(f'<text x="{LEFT + w * STEP}" y="{TOP - 6}">{MONTHS[first.month - 1]}</text>')
            last_label_week = w
        prev_month = first.month

    for row, name in ((1, "Mon"), (3, "Wed"), (5, "Fri")):
        out.append(f'<text x="0" y="{TOP + row * STEP + CELL - 1}">{name}</text>')

    for d in days:
        i = (d - start).days
        x, y = LEFT + (i // 7) * STEP, TOP + (i % 7) * STEP
        n = values[d]
        out.append(
            f'<rect x="{x}" y="{y}" width="{CELL}" height="{CELL}" rx="2" class="l{level(n, max_count)}">'
            f"<title>{n} on {d.isoformat()}</title></rect>"
        )

    ly = TOP + 7 * STEP + 10
    lx = width - 4 - 5 * STEP - 56
    out.append(f'<text x="{lx}" y="{ly + CELL - 1}">Less</text>')
    for i in range(5):
        out.append(f'<rect x="{lx + 26 + i * STEP}" y="{ly}" width="{CELL}" height="{CELL}" rx="2" class="l{i}"/>')
    out.append(f'<text x="{lx + 26 + 5 * STEP + 2}" y="{ly + CELL - 1}">More</text>')
    out.append("</svg>")
    return "\n".join(out) + "\n"


def main():
    token = os.environ.get("GH_TOKEN")
    personal = os.environ.get("PERSONAL_LOGIN")
    work_login = os.environ.get("WORK_LOGIN")
    if not token or not personal:
        sys.exit("Set GH_TOKEN and PERSONAL_LOGIN")

    counts = fetch_calendar(personal, token)

    work = load_work_file()
    if work_login:
        for day, n in fetch_calendar(work_login, token).items():
            work[day] = max(work.get(day, 0), n)
    for day, n in work.items():
        counts[day] = counts.get(day, 0) + n

    OUT_FILE.write_text(render(counts, date.today()))
    print(f"Wrote {OUT_FILE.name}")


if __name__ == "__main__":
    main()
