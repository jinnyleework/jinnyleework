#!/usr/bin/env python3
"""Build combined-graph.svg: personal GitHub contributions + work contributions.

Env:
  GH_TOKEN        token for the GitHub GraphQL API (the Action's own token works)
  PERSONAL_LOGIN  personal GitHub username
  WORK_LOGIN      optional work username; its public calendar is merged with
                  data/work-contributions.json, taking the larger count per day
"""
import hashlib
import json
import math
import os
import re
import sys
import urllib.request
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WORK_FILE = ROOT / "data" / "work-contributions.json"
OUT_DIR = ROOT
README = ROOT / "README.md"

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

WIDTH = 900
LEFT = 32           # weekday label gutter
GAP = 3
HEAT_TOP = 112      # first heatmap row
BAR_H = 44          # weekly bar strip height
MONTHS = "Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split()
FONT = '-apple-system,BlinkMacSystemFont,"Segoe UI",Helvetica,Arial,sans-serif'

# One file per GitHub theme: an <img> can't see GitHub's theme, only the OS
# one, so the README picks the file with <picture>.
THEMES = {
    "light": "--t1:#1f2328;--t2:#59636e;--personal:#e16f24;--work:#0969da;"
             "--l0:#eff2f5;--l1:#aceebb;--l2:#4ac26b;--l3:#2da44e;--l4:#116329",
    "dark": "--t1:#f0f6fc;--t2:#9198a1;--personal:#db6d28;--work:#4493f8;"
            "--l0:#151b23;--l1:#033a16;--l2:#196c2e;--l3:#2ea043;--l4:#56d364",
}

STYLE = f"""
text{{font:10px {FONT};fill:var(--t2)}}
.big{{font-size:30px;font-weight:600;fill:var(--t1)}}
.num{{font-size:18px;font-weight:600;fill:var(--t1)}}
.cap{{font-size:11px}}
.l0{{fill:var(--l0)}}.l1{{fill:var(--l1)}}.l2{{fill:var(--l2)}}.l3{{fill:var(--l3)}}.l4{{fill:var(--l4)}}
.p{{fill:var(--personal)}}.w{{fill:var(--work)}}.track{{fill:var(--l0)}}
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


def scale_cap(counts):
    # GitHub ignores outlier days when shading: its levels match quarters of
    # roughly the 92nd percentile of active days, not quarters of the max.
    active = sorted(n for n in counts if n)
    if not active:
        return 1
    k = (len(active) - 1) * 0.92
    lo = math.floor(k)
    hi = min(lo + 1, len(active) - 1)
    return max(1, math.ceil(active[lo] + (active[hi] - active[lo]) * (k - lo)))


def level(count, cap):
    return 0 if count == 0 else min(4, math.ceil(4 * count / cap))


def plural(n, word):
    return f"{n:,} {word}{'' if n == 1 else 's'}"


def render(personal, work, end, theme="light"):
    start = end - timedelta(days=364)
    start -= timedelta(days=(start.weekday() + 1) % 7)  # back to Sunday
    days = [start + timedelta(days=i) for i in range((end - start).days + 1)]
    n_weeks = len(days) // 7 + (1 if len(days) % 7 else 0)

    p = {d: personal.get(d.isoformat(), 0) for d in days}
    w = {d: work.get(d.isoformat(), 0) for d in days}
    total_p, total_w = sum(p.values()), sum(w.values())
    total = total_p + total_w
    cap = scale_cap([p[d] + w[d] for d in days])

    step = (WIDTH - LEFT) / n_weeks
    cell = step - GAP
    heat_bottom = HEAT_TOP + 7 * step - GAP
    bar_base = heat_bottom + 22 + BAR_H
    legend_y = bar_base + 24
    height = legend_y + 6

    out = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" height="{height:.0f}" '
        f'viewBox="0 0 {WIDTH} {height:.0f}" role="img" '
        f'aria-label="{total} contributions in the last year: {total_p} personal, {total_w} work">',
        f"<style>svg{{{THEMES[theme]}}}{STYLE}</style>",
    ]

    # Header: total, then personal and work with their share.
    out.append('<text class="cap" x="0" y="14">Contributions in the last year · personal + work</text>')
    out.append(f'<text class="big" x="0" y="50">{total:,}</text>')
    for i, (label, cls, n) in enumerate((("Work", "w", total_w), ("Personal", "p", total_p))):
        x = WIDTH - 150 * (i + 1) + 20
        share = f"{round(100 * n / total)}%" if total else "–"
        out.append(f'<rect x="{x}" y="5" width="10" height="10" rx="2" class="{cls}"/>')
        out.append(f'<text class="cap" x="{x + 16}" y="14">{label}</text>')
        out.append(f'<text class="num" x="{x}" y="46">{n:,}<tspan class="cap" dx="6">{share}</tspan></text>')

    # Share bar: personal then work, 2px gap between.
    bar_y = 64
    if total:
        pw = WIDTH * total_p / total
        if total_p:
            out.append(f'<rect x="0" y="{bar_y}" width="{pw - (2 if total_w else 0):.1f}" height="6" rx="3" class="p"/>')
        if total_w:
            x = pw + (2 if total_p else 0)
            out.append(f'<rect x="{x:.1f}" y="{bar_y}" width="{WIDTH - x:.1f}" height="6" rx="3" class="w"/>')
    else:
        out.append(f'<rect x="0" y="{bar_y}" width="{WIDTH}" height="6" rx="3" class="track"/>')

    # Month labels.
    last_label, prev_month = -3, None
    for wk in range(n_weeks):
        first = start + timedelta(weeks=wk)
        if first.month != prev_month and wk - last_label >= 3:
            out.append(f'<text x="{LEFT + wk * step:.1f}" y="{HEAT_TOP - 8}">{MONTHS[first.month - 1]}</text>')
            last_label = wk
        prev_month = first.month

    for row, name in ((1, "Mon"), (3, "Wed"), (5, "Fri")):
        out.append(f'<text x="0" y="{HEAT_TOP + row * step + cell - 2:.1f}">{name}</text>')

    # Heatmap of combined counts; each cell's tooltip shows the split.
    for d in days:
        i = (d - start).days
        x, y = LEFT + (i // 7) * step, HEAT_TOP + (i % 7) * step
        n = p[d] + w[d]
        tip = f"{d:%b} {d.day}, {d.year}: {plural(n, 'contribution')} (personal {p[d]}, work {w[d]})"
        out.append(
            f'<rect x="{x:.1f}" y="{y:.1f}" width="{cell:.1f}" height="{cell:.1f}" rx="2" '
            f'class="l{level(n, cap)}"><title>{tip}</title></rect>'
        )

    # Weekly bars: personal on the baseline, work stacked above.
    weekly = []
    for wk in range(n_weeks):
        week_days = days[wk * 7:(wk + 1) * 7]
        weekly.append((sum(p[d] for d in week_days), sum(w[d] for d in week_days), week_days[0]))
    max_week = max((a + b for a, b, _ in weekly), default=0) or 1
    out.append(f'<text x="0" y="{bar_base - BAR_H + 8:.1f}">{max_week:,}</text>')
    out.append(f'<text x="0" y="{bar_base:.1f}">0</text>')
    out.append(f'<text x="0" y="{bar_base - BAR_H / 2 + 4:.1f}" class="cap">/wk</text>')
    for wk, (a, b, first) in enumerate(weekly):
        x = LEFT + wk * step
        tip = f"Week of {first:%b} {first.day}: personal {a}, work {b}"
        out.append(f'<g><title>{tip}</title>')
        out.append(f'<rect x="{x:.1f}" y="{bar_base - BAR_H:.1f}" width="{cell:.1f}" height="{BAR_H}" fill="none" pointer-events="all"/>')
        top = bar_base
        for n, cls in ((a, "p"), (b, "w")):
            if not n:
                continue
            h = max(2, BAR_H * n / max_week)
            if top < bar_base:
                top -= 2  # surface gap between segments
            top -= h
            out.append(f'<rect x="{x:.1f}" y="{top:.1f}" width="{cell:.1f}" height="{h:.1f}" rx="1.5" class="{cls}"/>')
        out.append("</g>")

    # Legends: series on the left, heatmap scale on the right.
    ly = legend_y - 9
    out.append(f'<rect x="{LEFT}" y="{ly}" width="10" height="10" rx="2" class="p"/>')
    out.append(f'<text x="{LEFT + 15}" y="{legend_y}">Personal</text>')
    out.append(f'<rect x="{LEFT + 75}" y="{ly}" width="10" height="10" rx="2" class="w"/>')
    out.append(f'<text x="{LEFT + 90}" y="{legend_y}">Work</text>')
    lx = WIDTH - 5 * 14 - 58
    out.append(f'<text x="{lx}" y="{legend_y}">Less</text>')
    for i in range(5):
        out.append(f'<rect x="{lx + 26 + i * 14}" y="{ly}" width="10" height="10" rx="2" class="l{i}"/>')
    out.append(f'<text x="{lx + 26 + 5 * 14 + 2}" y="{legend_y}">More</text>')

    out.append("</svg>")
    return "\n".join(out) + "\n"


def main():
    token = os.environ.get("GH_TOKEN")
    personal_login = os.environ.get("PERSONAL_LOGIN")
    work_login = os.environ.get("WORK_LOGIN")
    if not token or not personal_login:
        sys.exit("Set GH_TOKEN and PERSONAL_LOGIN")

    personal = fetch_calendar(personal_login, token)

    work = load_work_file()
    if work_login:
        for day, n in fetch_calendar(work_login, token).items():
            work[day] = max(work.get(day, 0), n)

    for theme in THEMES:
        out = OUT_DIR / f"combined-graph-{theme}.svg"
        svg = render(personal, work, date.today(), theme)
        out.write_text(svg)
        print(f"Wrote {out.name}")
        bust_cache(out.name, hashlib.sha1(svg.encode()).hexdigest()[:8])


def bust_cache(name, version):
    # GitHub caches raw files for 5 minutes per URL, so give the README a new
    # URL whenever the graph changes.
    if not README.exists():
        return
    text = README.read_text()
    updated = re.sub(rf"{re.escape(name)}(\?v=\w+)?", f"{name}?v={version}", text)
    if updated != text:
        README.write_text(updated)


if __name__ == "__main__":
    main()
