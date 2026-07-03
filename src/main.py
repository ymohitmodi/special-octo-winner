"""nyx-promoter: generate + publish social content for a GitHub project.

Run once (Task Scheduler calls this daily):
    python src/main.py
Preview without posting anything:
    python src/main.py --dry-run
Force a weekly digest even if it's not digest day:
    python src/main.py --force-digest
"""
import argparse
import sys
from datetime import date
from pathlib import Path

import generate
import github_source as gh
from config import load_config
from publishers import PUBLISHERS
from state import State

ROOT = Path(__file__).resolve().parent.parent
DRAFTS = ROOT / "drafts"

WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


def collect_items(cfg: dict, state: State, force_digest: bool) -> list[dict]:
    """Decide what there is to talk about today. Each item posts at most once per platform."""
    repo = cfg["project"]["repo"]
    items = []

    if cfg["content"].get("release_announcements"):
        rel = gh.latest_release(repo)
        if rel and not rel.get("draft") and not rel.get("prerelease"):
            tag = rel.get("tag_name", "")
            item_id = f"release:{tag}"
            items.append({
                "id": item_id,
                "kind": "new release",
                "title": rel.get("name") or tag,
                "context": (rel.get("body") or "(no release notes)")[:4000],
                "url": rel.get("html_url"),
            })

    if cfg["content"].get("weekly_digest"):
        digest_day = cfg["content"].get("digest_weekday", "Friday")
        if force_digest or WEEKDAYS[date.today().weekday()] == digest_day:
            days = cfg["content"].get("digest_lookback_days", 7)
            commits = gh.recent_commits(repo, days)
            summary = gh.commit_summary(commits)
            if summary:
                items.append({
                    "id": f"digest:{date.today().isoformat()}",
                    "kind": f"development digest (last {days} days)",
                    "title": f"This week in {cfg['project']['name']}",
                    "context": summary,
                    "url": cfg["project"]["homepage"],
                })
            else:
                print(f"[digest] no commits in the last {days} days, skipping")

    return items


def write_draft(platform: str, item: dict, text: str) -> Path:
    DRAFTS.mkdir(exist_ok=True)
    safe_id = item["id"].replace(":", "-").replace("/", "-")
    path = DRAFTS / f"{date.today().isoformat()}-{safe_id}-{platform}.md"
    path.write_text(
        f"<!-- platform: {platform} | item: {item['id']} | review, edit, then post manually -->\n\n{text}\n",
        encoding="utf-8",
    )
    return path


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate and publish posts about the project")
    parser.add_argument("--dry-run", action="store_true", help="print posts, don't publish or save state")
    parser.add_argument("--force-digest", action="store_true", help="build the digest regardless of weekday")
    args = parser.parse_args()

    cfg = load_config()
    state = State.load()
    cap = cfg["content"].get("max_auto_posts_per_day", 3)

    items = collect_items(cfg, state, args.force_digest)
    if not items:
        print("Nothing new to post about.")
        return 0

    enabled = {
        name: pcfg for name, pcfg in cfg["platforms"].items()
        if pcfg.get("enabled")
    }
    if not enabled:
        print("No platforms enabled in config.yaml — enable at least one.")
        return 0

    failures = 0
    for item in items:
        for name, pcfg in enabled.items():
            if state.already_done(item["id"], name):
                continue
            mode = pcfg.get("mode", "draft")
            if mode == "auto" and state.auto_posts_today() >= cap:
                print(f"[{name}] daily auto-post cap ({cap}) reached, leaving {item['id']} for tomorrow")
                continue

            try:
                if name == "devto":
                    title, body = generate.generate_article(cfg, item)
                    text = f"{title}\n\n{body}"
                else:
                    text = generate.generate_post(cfg, name, item)
            except Exception as e:
                print(f"[{name}] generation failed for {item['id']}: {e}", file=sys.stderr)
                failures += 1
                continue

            if args.dry_run:
                print(f"\n--- {name} / {item['id']} ({mode}) ---\n{text}\n")
                continue

            try:
                if mode == "auto":
                    result = PUBLISHERS[name](pcfg, text, item)
                    state.record_auto_post()
                    print(f"[{name}] published {item['id']}: {result}")
                else:
                    path = write_draft(name, item, text)
                    print(f"[{name}] draft written for {item['id']}: {path}")
                state.mark_done(item["id"], name)
                state.save()
            except Exception as e:
                print(f"[{name}] publish failed for {item['id']}: {e}", file=sys.stderr)
                failures += 1

    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
