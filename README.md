# nyx-promoter

Automated content pipeline that promotes the [nyx](https://github.com/ymohitmodi/upgraded-palm-tree)
GitHub project on social media. Designed to run unattended on a Windows 11 mini PC,
using **Ollama cloud models** for content generation — no paid LLM API needed.

## What it does

Once a day (Windows Task Scheduler):

1. **Watches the nyx repo** via the GitHub API for new releases and recent commits.
2. **Generates platform-tailored posts** with your Ollama model (release announcements,
   weekly "this week in nyx" digests, and a long-form dev.to article per event).
3. **Publishes automatically** to platforms where that's safe and allowed
   (Bluesky, Mastodon, dev.to, Discord, Telegram), and **writes review drafts**
   to `drafts/` for platforms where automation is risky (X free tier, Reddit).
4. **Never double-posts** (state tracking) and **rate-limits itself**
   (default: max 3 automated posts/day across all platforms).

## The best content: nyx showcasing itself

The highest-signal posts don't *describe* nyx — they *are* nyx working. On its
scheduled day the promoter runs nyx in one of the domains it's genuinely strong
at and posts the real artifact, rotating week to week:

| nyx strength | What it runs | What gets posted |
|--------------|--------------|------------------|
| **Software** | `nyx build "<intent>"` (supervised — **held for approval, never auto-shipped**) | The full gated SDLC pipeline running end-to-end, with audited run metrics and the governance gate holding the deploy |
| **Value investing** | `nyx backtest` (read-only analysis) | nyx screening for deep value, and its Constitution *auto-rejecting* a "guaranteed returns" memo — governance as the hook |
| **Advisor** | `nyx run "<EB-1 / solo-SaaS goal>"` (1 bounded cycle) | An ambiguous goal decomposed into concrete gated deliverables |

Two hard safety rules are baked in and shouldn't be relaxed:

- **The approval gate is never disabled.** Software showcases run supervised and
  end in `HELD` — nyx demonstrates the pipeline without shipping anything
  unattended. That the build *waits for a human* is part of the story.
- **No performance claims, ever.** Investing/advisor posts pass through a
  guardrail that rejects any text implying guaranteed or risk-free returns and
  appends a "Not financial advice" disclaimer. This mirrors nyx's own
  Constitution, which forbids promising returns.

Configure it under `showcase:` in `config.yaml` (point `nyx_dir` at your nyx
checkout, list the intents/objectives to demo). It uses your Ollama Cloud key
when set, so the posted artifacts are real model output — not mock data.

### Proof of autonomous work (the receipts)

On its own weekday the promoter reads nyx's **tamper-evident, hash-chained
audit ledger** and posts a verifiable summary: how many constitutional gates
passed, how many were blocked, across how many specialized agents, and whether
the hash chain verifies intact. This is nyx's strongest trust signal — not a
claim about autonomy, a cryptographic record of it. Enabled under
`showcase.proof_of_work`.

### Reach: nyx-written threads

nyx showcases and proof-of-work posts go out as native **reply-chain threads**
on X and Bluesky (single posts elsewhere) — a hook, the substance, then a call
to action with the link. Threads reach far more people than one post, and a
thread counts as a single item against the daily cap. Toggle under `reach:`.

Reach here means *legitimate distribution only* — threads, discoverability,
posting real work. There is deliberately no follow/unfollow botting, mass DMing,
or fake engagement; those get accounts suppressed, which is the opposite of the
goal.

Preview everything without posting:

```powershell
.\scripts\run.ps1 --dry-run --force-showcase
```

## Generic: auto-marketing anything nyx produces

The showcases above are built-in, but the pipeline is **content-source driven**,
so it markets *any* auto-generated output from nyx without new code. nyx (running
autonomously) drops a marketing-ready artifact into an **outbox** directory, and
the promoter discovers it, writes platform-tailored posts, and publishes:

```
nyx produces output ──▶ nyx_outbox/*.{json,md,txt} ──▶ generate → publish → archive
```

An artifact is just a file. Minimal example (`nyx_outbox/note.md`):

```markdown
---
kind: market note
strength: investing
guardrails: [no_return_promise]
platforms: [bluesky, linkedin]
thread: true
---
The auto-generated content the post is written from …
```

Or nyx emits one directly from its own code:

```python
from outbox import write_artifact
write_artifact("nyx_outbox", kind="shipped feature", title=headline,
               context=summary, strength="software")
```

Each artifact can target a subset of platforms, opt in/out of threading, and
declare guardrails — all enforced. Published artifacts are archived to
`nyx_outbox/published/`. Full contract in [docs/OUTBOX.md](docs/OUTBOX.md).

Sources are configured (and reorderable) under `sources:` in `config.yaml`;
adding a brand-new *kind* of source is a few lines in `src/sources.py` via the
`@source("name")` registry. Built-in sources: `github_release`, `commit_digest`,
`nyx_showcase`, `nyx_proof`, `nyx_outbox`.

## Setup (Windows 11)

Prereqs: [Python 3.11+](https://python.org), [Ollama](https://ollama.com) with a
cloud model pulled (e.g. `ollama pull gpt-oss:120b-cloud`), and Ollama running.

```powershell
git clone https://github.com/ymohitmodi/special-octo-winner
cd special-octo-winner
powershell -ExecutionPolicy Bypass -File scripts\install_windows.ps1 -Time "18:00"
```

Then:

1. **Edit `config.yaml`** — most importantly, write a real `project.pitch`
   describing what nyx does (post quality depends on it), and set
   `enabled: true` on the platforms you use.
2. **Edit `.env`** — paste API keys for those platforms (`.env.example`
   documents where to get each one).
3. **Test without posting:**
   ```powershell
   .\scripts\run.ps1 --dry-run --force-digest
   ```
4. When the output looks good, you're done — the scheduled task takes it from here.

## Platform notes

| Platform | Default mode | Why |
|----------|--------------|-----|
| Bluesky, Mastodon | auto | Free open APIs, dev-heavy audiences |
| dev.to | auto | Long-form articles, good SEO for the repo |
| Discord, Telegram | auto | Your own community channels |
| LinkedIn | auto | Official Posts API; strong reach for a technical project (profile or company page) |
| X / Twitter | auto | Fully autonomous (incl. threads); free API tier caps ~500 posts/mo |
| Reddit | draft only | Automated self-promo violates most subreddit rules and gets you banned — kept draft on purpose |

## What this deliberately does NOT do

No auto-follow/unfollow, no mass DMs, no fake engagement, no cross-posting the same
text into communities you're not part of. That behavior violates platform terms of
service and gets accounts suppressed or banned — the opposite of growing a project.
This tool only publishes honest content about real project activity, at a low rate,
through official APIs, on accounts you own.

## Handy commands

```powershell
.\scripts\run.ps1 --dry-run          # preview today's posts, publish nothing
.\scripts\run.ps1 --force-digest     # build the weekly digest right now
.\scripts\run.ps1 --force-showcase   # run a nyx self-showcase right now
.\scripts\run.ps1                    # normal run (what the scheduled task does)
```

State lives in `state.json` (delete it to allow re-posting), drafts in `drafts/`.
Both are gitignored.
