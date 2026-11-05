#!/usr/bin/env python3
"""Generate STAN-styled GitHub profile stat cards from live GitHub data.

Queries the GraphQL contributionsCollection (last 365 days) for total
contributions, best day (highest one-day), current streak and longest
streak, plus REST user/repo metrics — then renders carbon #070708 SVGs with
#ff2d55 accents. Output: dist/stats-card.svg, dist/metrics-card.svg. Stdlib only; GITHUB_TOKEN from env.
"""
import json
import os
import urllib.request
from datetime import datetime, timedelta, timezone

OWNER = os.environ.get("GITHUB_REPOSITORY_OWNER", "mxsourav")
TOKEN = os.environ["GITHUB_TOKEN"]
DIST = "dist"
os.makedirs(DIST, exist_ok=True)
CARBON, BORDER, RED, WHITE, GRAY, DIM = "#070708", "#26262B", "#FF2D55", "#FFFFFF", "#C9C9CF", "#8B8B93"


def api(url, payload=None):
    body = None
    if payload:
        body = json.dumps(payload).encode()
    req = urllib.request.Request(url, data=body, method="POST" if payload else "GET")
    req.add_header("Authorization", f"Bearer {TOKEN}")
    req.add_header("Accept", "application/vnd.github+json")
    req.add_header("User-Agent", "stan-profile-cards")
    if payload:
        req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read())


since = (datetime.now(timezone.utc) - timedelta(days=365)).strftime("%Y-%m-%dT%H:%M:%SZ")
query = """
query($login: String!, $since: DateTime!) {
  user(login: $login) {
    contributionsCollection(from: $since) {
      contributionCalendar { totalContributions weeks { contributionDays { contributionCount date } } }
    }
  }
}"""
data = api("https://api.github.com/graphql", {"query": query, "variables": {"login": OWNER, "since": since}})
cal = data["data"]["user"]["contributionsCollection"]["contributionCalendar"]
days = [d for w in cal["weeks"] for d in w["contributionDays"]]
total = cal["totalContributions"]

best_day, best_date = max(((d["contributionCount"], d["date"]) for d in days), key=lambda t: t[0])

def streaks(days_list):
    longest = cur = 0
    for d in days_list:
        cur = cur + 1 if d["contributionCount"] > 0 else 0
        longest = max(longest, cur)
    current = 0
    for d in reversed(days_list):
        if d["contributionCount"] > 0:
            current += 1
        elif d is days_list[-1]:
            continue  # today still open — don't break the streak on a zero today
        else:
            break
    return current, longest

current, longest = streaks(days)
range_label = f"{datetime.fromisoformat(days[0]['date'].replace('Z','+00:00')).strftime('%b %d %Y')} — NOW".upper()

user = api(f"https://api.github.com/users/{OWNER}")
repos = api(f"https://api.github.com/users/{OWNER}/repos?per_page=100&sort=updated")
stars = sum(r.get("stargazers_count", 0) for r in repos)
years_on_github = max(1, (datetime.now(timezone.utc) - datetime.fromisoformat(user["created_at"].replace("Z", "+00:00"))).days // 365)

def esc(s):
    return s.replace("&", "&amp;").replace("<", "&lt;")

def stat_block(cx, value, label, value_color=WHITE, size=30):
    return (f'<text x="{cx}" y="118" text-anchor="middle" font-family="JetBrains Mono,ui-monospace,monospace" '
            f'font-size="{size}" font-weight="700" fill="{value_color}">{esc(str(value))}</text>'
            f'<text x="{cx}" y="146" text-anchor="middle" font-family="JetBrains Mono,ui-monospace,monospace" '
            f'font-size="10.5" letter-spacing="2" fill="{DIM}">{esc(label.upper())}</text>')

def card_scaffold(w, h, inner):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" role="img">'
            f'<rect x="1" y="1" width="{w - 2}" height="{h - 2}" rx="18" fill="{CARBON}" stroke="{BORDER}"/>'
            f'<rect x="1" y="1" width="{w - 2}" height="{h - 2}" rx="18" fill="none" stroke="url(#g)" opacity="0.5"/>'
            f'<defs><linearGradient id="g" x1="0" y1="0" x2="0" y2="1">'
            f'<stop offset="0" stop-color="#ffffff" stop-opacity="0.14"/>'
            f'<stop offset="1" stop-color="#ffffff" stop-opacity="0"/></linearGradient></defs>'
            f'<rect x="26" y="24" width="9" height="9" rx="2.5" fill="{RED}"/>'
            f'<text x="44" y="33" font-family="JetBrains Mono,ui-monospace,monospace" font-size="12" '
            f'font-weight="700" letter-spacing="3" fill="{WHITE}">STAN</text>'
            + inner + "</svg>")

# ── stats card: the headline numbers ─────────────────────────────────────────
stats_inner = (
    f'<text x="614" y="33" text-anchor="end" font-family="JetBrains Mono,ui-monospace,monospace" '
    f'font-size="9.5" letter-spacing="1.5" fill="{DIM}">{esc(range_label)}</text>'
    + stat_block(110, f"{total:,}", "contributions · 1y")
    + stat_block(275, best_day, "best day", RED)
    + stat_block(430, f"{current}d", "current streak")
    + stat_block(565, f"{longest}d", "longest streak")
    + f'<text x="275" y="168" text-anchor="middle" font-family="JetBrains Mono,ui-monospace,monospace" '
      f'font-size="9.5" fill="{DIM}">{esc(datetime.fromisoformat(best_date.replace("Z", "+00:00")).strftime("%b %d, %Y").upper())}</text>'
)
with open(f"{DIST}/stats-card.svg", "w", encoding="utf-8") as f:
    f.write(card_scaffold(660, 190, stats_inner))

# ── metrics card: repos / stars / followers / years ──────────────────────────
metrics_inner = (
    stat_block(110, user.get("public_repos", 0), "public repos")
    + stat_block(275, stars, "stars")
    + stat_block(430, user.get("followers", 0), "followers")
    + stat_block(565, f"{years_on_github}y", "on github")
)
with open(f"{DIST}/metrics-card.svg", "w", encoding="utf-8") as f:
    f.write(card_scaffold(660, 190, metrics_inner))

print(f"cards written: total={total} best={best_day} ({best_date}) streak={current}/{longest} repos={user.get('public_repos')} stars={stars}")
