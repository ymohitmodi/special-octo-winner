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
| X / Twitter | draft | Free API tier is ~500 posts/mo; flip to `auto` in config once keys work |
| Reddit | draft only | Automated self-promo violates most subreddit rules — always post by hand |

## What this deliberately does NOT do

No auto-follow/unfollow, no mass DMs, no fake engagement, no cross-posting the same
text into communities you're not part of. That behavior violates platform terms of
service and gets accounts suppressed or banned — the opposite of growing a project.
This tool only publishes honest content about real project activity, at a low rate,
through official APIs, on accounts you own.

## Handy commands

```powershell
.\scripts\run.ps1 --dry-run        # preview today's posts, publish nothing
.\scripts\run.ps1 --force-digest   # build the weekly digest right now
.\scripts\run.ps1                  # normal run (what the scheduled task does)
```

State lives in `state.json` (delete it to allow re-posting), drafts in `drafts/`.
Both are gitignored.
