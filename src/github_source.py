"""Read project activity from the GitHub REST API (read-only)."""
from datetime import datetime, timedelta, timezone

import requests

from config import env

API = "https://api.github.com"


def _get(path: str, params: dict | None = None):
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "nyx-promoter",
    }
    token = env("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    r = requests.get(f"{API}{path}", headers=headers, params=params, timeout=30)
    if r.status_code == 404:
        return None
    r.raise_for_status()
    return r.json()


def repo_info(repo: str) -> dict | None:
    return _get(f"/repos/{repo}")


def latest_release(repo: str) -> dict | None:
    return _get(f"/repos/{repo}/releases/latest")


def recent_commits(repo: str, days: int) -> list[dict]:
    since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    commits = _get(f"/repos/{repo}/commits", params={"since": since, "per_page": 50})
    return commits or []


def commit_summary(commits: list[dict], limit: int = 25) -> str:
    """First line of each commit message, newest first."""
    lines = []
    for c in commits[:limit]:
        msg = c.get("commit", {}).get("message", "").split("\n")[0].strip()
        if msg:
            lines.append(f"- {msg}")
    return "\n".join(lines)
