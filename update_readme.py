"""
update_readme.py
Pulls live GitHub stats for shishirastogi and writes them into README.md
between the <!--STATS:START--> / <!--STATS:END--> markers.

Run manually:
    GH_TOKEN=your_token python update_readme.py

In GitHub Actions, the built-in secrets.GITHUB_TOKEN is enough for public data.
"""

import os
import sys
from datetime import datetime, timezone

import requests

USERNAME = "shishirastogi"
TOKEN = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")

if not TOKEN:
    sys.exit("Missing GH_TOKEN / GITHUB_TOKEN environment variable.")

HEADERS = {"Authorization": f"Bearer {TOKEN}", "Accept": "application/vnd.github+json"}
API = "https://api.github.com"


def get_user():
    r = requests.get(f"{API}/users/{USERNAME}", headers=HEADERS)
    r.raise_for_status()
    return r.json()


def get_all_repos():
    repos = []
    page = 1
    while True:
        r = requests.get(
            f"{API}/users/{USERNAME}/repos",
            headers=HEADERS,
            params={"per_page": 100, "page": page, "type": "owner"},
        )
        r.raise_for_status()
        batch = r.json()
        if not batch:
            break
        repos.extend(batch)
        page += 1
        if page > 10:  # safety cap, 1000 repos
            break
    return repos


def get_commit_count():
    """Total commit contributions in the last year, via GraphQL."""
    query = """
    query($login: String!) {
      user(login: $login) {
        contributionsCollection {
          totalCommitContributions
        }
      }
    }
    """
    try:
        r = requests.post(
            f"{API}/graphql",
            headers=HEADERS,
            json={"query": query, "variables": {"login": USERNAME}},
        )
        r.raise_for_status()
        data = r.json()["data"]["user"]["contributionsCollection"]
        return data["totalCommitContributions"]
    except Exception:
        return None


def format_uptime(created_at):
    created = datetime.strptime(created_at, "%Y-%m-%dT%H:%M:%SZ").replace(
        tzinfo=timezone.utc
    )
    now = datetime.now(timezone.utc)
    days = (now - created).days
    years, remainder = divmod(days, 365)
    months = remainder // 30
    return f"{years} years, {months} months"


def top_languages(repos, n=4):
    counts = {}
    for repo in repos:
        lang = repo.get("language")
        if lang and not repo.get("fork"):
            counts[lang] = counts.get(lang, 0) + 1
    ranked = sorted(counts.items(), key=lambda x: x[1], reverse=True)
    return ", ".join(lang for lang, _ in ranked[:n]) or "—"


def build_stats_block():
    user = get_user()
    repos = get_all_repos()

    stars = sum(r.get("stargazers_count", 0) for r in repos)
    forks = sum(r.get("forks_count", 0) for r in repos)
    commits = get_commit_count()

    lines = [
        f"{'OS:':<12}GitHub",
        f"{'Uptime:':<12}{format_uptime(user['created_at'])}",
        f"{'Languages:':<12}{top_languages(repos)}",
        "-" * 38,
        f"{'Repos:':<12}{user['public_repos']:<10}{'Stars:':<10}{stars}",
        f"{'Followers:':<12}{user['followers']:<10}{'Following:':<10}{user['following']}",
        f"{'Forks:':<12}{forks}",
    ]
    if commits is not None:
        lines.append(f"{'Commits:':<12}{commits} (last year)")

    return "\n".join(lines)


def update_readme(stats_block, path="README.md"):
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()

    start_marker = "<!--STATS:START-->"
    end_marker = "<!--STATS:END-->"

    if start_marker not in content or end_marker not in content:
        sys.exit("Markers not found in README.md — cannot update stats.")

    before = content.split(start_marker)[0]
    after = content.split(end_marker)[1]

    new_content = (
        f"{before}{start_marker}\n```text\n{stats_block}\n```\n{end_marker}{after}"
    )

    with open(path, "w", encoding="utf-8") as f:
        f.write(new_content)


if __name__ == "__main__":
    block = build_stats_block()
    update_readme(block)
    print("README.md updated.")
