"""Pluggable content sources.

A *source* yields marketing items. Each is registered by name and can be
enabled/scheduled from config, so adding a new content type is either:

  * dropping a file in the nyx outbox (zero code — the generic path), or
  * writing a small ``@source("name")`` function here (a few lines).

Every item is a dict: {id, kind, title, context, url, strength?, guardrails?,
platforms?, thread?}. ``id`` is the dedupe key (posted at most once per platform).
"""
from __future__ import annotations

import sys
from dataclasses import dataclass
from datetime import date
from typing import Callable, Iterable

import github_source as gh
import nyx_engine
import outbox

WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

SOURCES: dict[str, Callable] = {}


def source(name: str):
    def deco(fn: Callable) -> Callable:
        SOURCES[name] = fn
        return fn
    return deco


@dataclass
class Ctx:
    today: date
    force_digest: bool
    force_showcase: bool

    def is_day(self, weekday_name: str, forced: bool) -> bool:
        return forced or WEEKDAYS[self.today.weekday()] == weekday_name


# --- built-in sources (existing behavior, now registered) -------------------

@source("github_release")
def _release(cfg: dict, sc: dict, ctx: Ctx) -> Iterable[dict]:
    if not cfg["content"].get("release_announcements"):
        return []
    rel = gh.latest_release(cfg["project"]["repo"])
    if not rel or rel.get("draft") or rel.get("prerelease"):
        return []
    tag = rel.get("tag_name", "")
    return [{
        "id": f"release:{tag}",
        "kind": "new release",
        "title": rel.get("name") or tag,
        "context": (rel.get("body") or "(no release notes)")[:4000],
        "url": rel.get("html_url"),
    }]


@source("commit_digest")
def _digest(cfg: dict, sc: dict, ctx: Ctx) -> Iterable[dict]:
    c = cfg["content"]
    if not c.get("weekly_digest"):
        return []
    if not ctx.is_day(c.get("digest_weekday", "Friday"), ctx.force_digest):
        return []
    days = c.get("digest_lookback_days", 7)
    summary = gh.commit_summary(gh.recent_commits(cfg["project"]["repo"], days))
    if not summary:
        print(f"[digest] no commits in the last {days} days, skipping")
        return []
    return [{
        "id": f"digest:{ctx.today.isoformat()}",
        "kind": f"development digest (last {days} days)",
        "title": f"This week in {cfg['project']['name']}",
        "context": summary,
        "url": cfg["project"]["homepage"],
    }]


@source("nyx_showcase")
def _showcase(cfg: dict, sc_entry: dict, ctx: Ctx) -> Iterable[dict]:
    sc = cfg.get("showcase", {})
    if not sc.get("enabled") or not ctx.is_day(sc.get("weekday", "Tuesday"), ctx.force_showcase):
        return []
    strengths = sc.get("strengths") or ["software"]
    week = ctx.today.isocalendar()[1]
    strength = strengths[week % len(strengths)]
    run_id = f"{ctx.today.isocalendar()[0]}w{week}-{strength}"
    return [nyx_engine.build_showcase(cfg, strength, run_id)]


@source("nyx_proof")
def _proof(cfg: dict, sc_entry: dict, ctx: Ctx) -> Iterable[dict]:
    sc = cfg.get("showcase", {})
    if not sc.get("proof_of_work"):
        return []
    if not ctx.is_day(sc.get("proof_weekday", "Thursday"), ctx.force_showcase):
        return []
    return [nyx_engine.proof_of_work(cfg, ctx.today.isoformat())]


@source("nyx_outbox")
def _outbox(cfg: dict, entry: dict, ctx: Ctx) -> Iterable[dict]:
    """Generic: market whatever auto-generated artifacts nyx dropped in the outbox."""
    ob = {**cfg.get("nyx_outbox", {}), **entry}
    if ob.get("enabled") is False:
        return []
    directory = ob.get("dir", "nyx_outbox")
    return outbox.read_artifacts(directory, cfg)


# --- driver -----------------------------------------------------------------

def _configured(cfg: dict) -> list[dict]:
    """The ordered list of sources to run. Defaults reproduce prior behavior
    plus the generic outbox, so existing configs keep working untouched."""
    entries = cfg.get("sources")
    if entries:
        return [e if isinstance(e, dict) else {"type": e} for e in entries]
    return [{"type": t} for t in
            ("github_release", "commit_digest", "nyx_showcase", "nyx_proof", "nyx_outbox")]


def collect(cfg: dict, ctx: Ctx) -> list[dict]:
    items: list[dict] = []
    for entry in _configured(cfg):
        stype = entry.get("type")
        fn = SOURCES.get(stype)
        if fn is None:
            print(f"[sources] unknown source type {stype!r}, skipping", file=sys.stderr)
            continue
        try:
            items.extend(fn(cfg, entry, ctx))
        except Exception as e:  # one bad source never sinks the run
            print(f"[sources] {stype} failed: {e}", file=sys.stderr)
    return items
