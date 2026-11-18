# Combined contribution graph

Shows personal + work GitHub activity as one heatmap in your profile README.

## 1. Copy into your profile repo
Copy `.github/`, `scripts/` and `data/` into the root of your profile README repo
(the public repo named after your personal username).

## 2. Add your work data
On your work machine, from the profile repo:

```
python3 scripts/export_work_commits.py --email you@company.com ~/path/to/work/repos
```

Use `--email` more than once if you've committed with several addresses.
Commit and push `data/work-contributions.json`. Re-run whenever you want to
refresh it (weekly is plenty); pushing the file rebuilds the graph.

You can also edit the JSON by hand: `{"2026-11-17": 4, "2026-11-18": 2}`.

## 3. Embed it in README.md

```
<picture>
  <source media="(prefers-color-scheme: dark)" srcset="./combined-graph-dark.svg">
  <img alt="Contributions in the last year" src="./combined-graph-light.svg" width="100%">
</picture>
```

GitHub swaps the light and dark files to match the viewer's GitHub theme.

## 4. Run it once
Repo → Actions → "Combined contribution graph" → Run workflow. After that it
runs daily.

## Optional settings
Repo → Settings → Secrets and variables → Actions → Variables:
- `PERSONAL_LOGIN`: only needed if the repo owner isn't your personal account
- `WORK_LOGIN`: also pulls the work account's public calendar; per day the
  larger of that and the JSON is used, so nothing is counted twice
