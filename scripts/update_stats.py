#!/usr/bin/env python3
"""
Fetches GitHub contribution stats for a user and regenerates assets/stats.svg.
Runs in GitHub Actions weekly. Uses the GraphQL API (needs GITHUB_TOKEN).
"""
import os
import sys
import json
import datetime
import urllib.request

USER = os.environ.get("GH_USER", "CanerCakal")
TOKEN = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
OUT = os.environ.get("OUT_PATH", "assets/stats.svg")

if not TOKEN:
    print("No token found; aborting.", file=sys.stderr)
    sys.exit(1)


def gql(query, variables):
    body = json.dumps({"query": query, "variables": variables}).encode()
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=body,
        headers={
            "Authorization": f"bearer {TOKEN}",
            "Content-Type": "application/json",
            "User-Agent": "stats-updater",
        },
    )
    with urllib.request.urlopen(req) as r:
        return json.load(r)


def iso(d):
    return d.strftime("%Y-%m-%dT00:00:00Z")


# Pull the last ~5 years of contribution calendars, one year at a time
today = datetime.date.today()
all_days = []  # (date, count)
total_contributions = 0

Q = """
query($login:String!, $from:DateTime!, $to:DateTime!){
  user(login:$login){
    contributionsCollection(from:$from, to:$to){
      contributionCalendar{
        totalContributions
        weeks{ contributionDays{ date contributionCount } }
      }
    }
  }
}
"""

for years_back in range(0, 5):
    to = today.replace(year=today.year - years_back)
    frm = to.replace(year=to.year - 1) + datetime.timedelta(days=1)
    data = gql(Q, {"login": USER, "from": iso(frm), "to": iso(to)})
    cal = (
        data.get("data", {})
        .get("user", {})
        .get("contributionsCollection", {})
        .get("contributionCalendar")
    )
    if not cal:
        continue
    total_contributions += cal["totalContributions"]
    for wk in cal["weeks"]:
        for day in wk["contributionDays"]:
            all_days.append((day["date"], day["contributionCount"]))

# Dedup + sort by date
seen = {}
for date, count in all_days:
    seen[date] = count
days = sorted(seen.items())

# --- compute streaks ---
current_streak = 0
current_start = None
longest_streak = 0
longest_start = longest_end = None

# current streak: walk backwards from most recent day with activity allowance for "today not yet committed"
run = 0
run_end = None
best = 0
best_s = best_e = None
run_s = None
for date, count in days:
    if count > 0:
        if run == 0:
            run_s = date
        run += 1
        run_end = date
        if run > best:
            best, best_s, best_e = run, run_s, date
    else:
        run = 0

longest_streak, longest_start, longest_end = best, best_s, best_e

# current streak = trailing run of active days (allow today=0 without breaking)
cur = 0
cur_start = None
for date, count in reversed(days):
    if count == 0:
        # if it's today and no commit yet, skip without breaking
        if date == today.strftime("%Y-%m-%d") and cur == 0:
            continue
        break
    cur += 1
    cur_start = date
current_streak = cur

first_date = days[0][0] if days else today.strftime("%Y-%m-%d")


def fmt(d):
    if not d:
        return "—"
    dt = datetime.datetime.strptime(d, "%Y-%m-%d")
    return dt.strftime("%b %d, %Y")


def fmt_short(d):
    if not d:
        return "—"
    dt = datetime.datetime.strptime(d, "%Y-%m-%d")
    return dt.strftime("%b %d")


total_start = fmt(first_date).rsplit(",", 1)[0]  # "Oct 23"
cur_range = f"{fmt_short(cur_start)} – {fmt_short(days[-1][0]) if cur else '—'}" if cur else "No active streak"
long_range = f"{fmt_short(longest_start)} – {fmt_short(longest_end)}"

# ring fraction for current streak (cap visual at 30 days)
frac = min(current_streak / 30.0, 1.0)
circ = 2 * 3.14159 * 42
dash_on = round(circ * frac, 1)
dash_off = round(circ - dash_on, 1)

svg = f'''<svg width="900" height="230" viewBox="0 0 900 230" fill="none" xmlns="http://www.w3.org/2000/svg" font-family="-apple-system, SF Pro Display, Segoe UI, Roboto, Helvetica, Arial, sans-serif">
  <defs>
    <linearGradient id="bg3" x1="0" y1="0" x2="900" y2="230" gradientUnits="userSpaceOnUse">
      <stop offset="0" stop-color="#0a0e1a"/><stop offset="1" stop-color="#0d1424"/>
    </linearGradient>
    <linearGradient id="acc3" x1="0" y1="0" x2="1" y2="0">
      <stop offset="0" stop-color="#F05138"/><stop offset="1" stop-color="#0A84FF"/>
    </linearGradient>
    <linearGradient id="ring" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0" stop-color="#0A84FF"/><stop offset="1" stop-color="#5E5CE6"/>
    </linearGradient>
    <clipPath id="c3"><rect x="1" y="1" width="898" height="228" rx="22"/></clipPath>
  </defs>
  <rect x="1" y="1" width="898" height="228" rx="22" fill="url(#bg3)" stroke="#1c2740" stroke-width="1.5"/>
  <g clip-path="url(#c3)">
    <g stroke="#141e33" stroke-width="1">
      <line x1="300" y1="40" x2="300" y2="200"/><line x1="600" y1="40" x2="600" y2="200"/>
    </g>
    <text x="40" y="48" fill="#ffffff" font-size="22" font-weight="800">GitHub Activity</text>
    <rect x="40" y="58" width="52" height="3" rx="1.5" fill="url(#acc3)"/>

    <g transform="translate(150,110)">
      <text x="0" y="0" fill="#ffffff" font-size="52" font-weight="800" text-anchor="middle">{total_contributions}</text>
      <text x="0" y="30" fill="#e6edf7" font-size="15" font-weight="600" text-anchor="middle">Total Contributions</text>
      <text x="0" y="54" fill="#5a6b8c" font-size="12" text-anchor="middle">{total_start} – Present</text>
    </g>

    <g transform="translate(450,105)">
      <circle cx="0" cy="0" r="42" fill="none" stroke="#1c2740" stroke-width="6"/>
      <circle cx="0" cy="0" r="42" fill="none" stroke="url(#ring)" stroke-width="6" stroke-linecap="round"
        stroke-dasharray="{dash_on} {dash_off}" transform="rotate(-90)">
        <animate attributeName="stroke-dasharray" values="0 {round(circ,1)};{dash_on} {dash_off}" dur="1.4s" fill="freeze"/>
      </circle>
      <path d="M0 -54 C4 -48 8 -46 6 -40 C10 -44 9 -50 0 -58 C-9 -50 -10 -44 -6 -40 C-8 -46 -4 -48 0 -54Z" fill="#F05138">
        <animate attributeName="opacity" values="0.7;1;0.7" dur="1.8s" repeatCount="indefinite"/>
      </path>
      <text x="0" y="14" fill="#ffffff" font-size="44" font-weight="800" text-anchor="middle">{current_streak}</text>
      <text x="0" y="66" fill="#0A84FF" font-size="15" font-weight="700" text-anchor="middle">Current Streak</text>
      <text x="0" y="88" fill="#5a6b8c" font-size="12" text-anchor="middle">{cur_range}</text>
    </g>

    <g transform="translate(750,110)">
      <text x="0" y="0" fill="#ffffff" font-size="52" font-weight="800" text-anchor="middle">{longest_streak}</text>
      <text x="0" y="30" fill="#e6edf7" font-size="15" font-weight="600" text-anchor="middle">Longest Streak</text>
      <text x="0" y="54" fill="#5a6b8c" font-size="12" text-anchor="middle">{long_range}</text>
    </g>

    <rect x="1" y="227" width="898" height="2" fill="url(#acc3)"/>
  </g>
</svg>
'''

os.makedirs(os.path.dirname(OUT), exist_ok=True)
with open(OUT, "w", encoding="utf-8") as f:
    f.write(svg)

print(f"Wrote {OUT}: total={total_contributions} current={current_streak} longest={longest_streak}")
