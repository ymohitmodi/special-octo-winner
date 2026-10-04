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
import nyx_engine
import outbox
import sources
from config import load_config
from publishers import PUBLISHERS, THREAD_PUBLISHERS
from state import State

ROOT = Path(__file__).resolve().parent.parent
DRAFTS = ROOT / "drafts"


def collect_items(cfg: dict, state: State, force_digest: bool, force_showcase: bool) -> list[dict]:
    """Gather items from every configured source. Each posts at most once per platform."""
    ctx = sources.Ctx(today=date.today(), force_digest=force_digest, force_showcase=force_showcase)
    return sources.collect(cfg, ctx)


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
    parser.add_argument("--force-showcase", action="store_true", help="run a nyx showcase regardless of weekday")
    args = parser.parse_args()

    cfg = load_config()
    state = State.load()
    cap = cfg["content"].get("max_auto_posts_per_day", 3)

    items = collect_items(cfg, state, args.force_digest, args.force_showcase)
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

    reach = cfg.get("reach", {})
    failures = 0
    for item in items:
        # An item may target a subset of platforms (self-describing, generic).
        targets = item.get("platforms")
        item_platforms = {
            n: p for n, p in enabled.items()
            if not targets or n in targets
        }
        published_any = False
        for name, pcfg in item_platforms.items():
            if state.already_done(item["id"], name):
                continue
            mode = pcfg.get("mode", "draft")
            if mode == "auto" and state.auto_posts_today() >= cap:
                print(f"[{name}] daily auto-post cap ({cap}) reached, leaving {item['id']} for tomorrow")
                continue

            # Threads (reach lever) apply on reply-chain platforms. An item can
            # opt in/out explicitly via `thread`; otherwise nyx strength items
            # thread by default when reach.threads is on.
            want_thread = item.get("thread")
            if want_thread is None:
                want_thread = bool(reach.get("threads") and item.get("strength"))
            use_thread = want_thread and name in THREAD_PUBLISHERS

            try:
                limit = generate.PLATFORM_SPECS.get(name, {}).get("limit", 500)
                if name == "devto":
                    title, body = generate.generate_article(cfg, item)
                    text, posts = f"{title}\n\n{body}", None
                elif use_thread:
                    posts = generate.generate_thread(
                        cfg, name, item, reach.get("max_thread_posts", 4))
                    posts = [nyx_engine.enforce_guardrails(item, p, limit) for p in posts]
                    text = "\n\n---\n\n".join(posts)
                else:
                    text = generate.generate_post(cfg, name, item)
                    text = nyx_engine.enforce_guardrails(item, text, limit)
                    posts = None
            except Exception as e:
                print(f"[{name}] generation failed for {item['id']}: {e}", file=sys.stderr)
                failures += 1
                continue

            if args.dry_run:
                kind = f"thread x{len(posts)}" if posts else "post"
                print(f"\n--- {name} / {item['id']} ({mode}, {kind}) ---\n{text}\n")
                continue

            try:
                if mode == "auto":
                    if posts:
                        result = THREAD_PUBLISHERS[name](pcfg, posts, item)
                    else:
                        result = PUBLISHERS[name](pcfg, text, item)
                    state.record_auto_post()  # a thread counts as one item
                    print(f"[{name}] published {item['id']}: {result}")
                else:
                    path = write_draft(name, item, text)
                    print(f"[{name}] draft written for {item['id']}: {path}")
                state.mark_done(item["id"], name)
                state.save()
                published_any = True
            except Exception as e:
                print(f"[{name}] publish failed for {item['id']}: {e}", file=sys.stderr)
                failures += 1

        # Archive fully-processed outbox artifacts so nyx's outbox stays clean.
        if published_any and item.get("_source_file") and cfg.get("nyx_outbox", {}).get("archive"):
            try:
                outbox.archive(item, cfg["nyx_outbox"].get("archive_dir", "nyx_outbox/published"))
            except Exception as e:
                print(f"[outbox] archive failed for {item['id']}: {e}", file=sys.stderr)

    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
