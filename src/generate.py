"""Generate platform-tailored posts with Ollama (local or cloud models)."""
import re

import requests

from config import env

# Per-platform shaping: character limit and style guidance for the model.
PLATFORM_SPECS = {
    "x": {
        "limit": 280,
        "style": "Punchy, no fluff, at most 2 hashtags. Write like a developer, not a marketer.",
    },
    "bluesky": {
        "limit": 300,
        "style": "Conversational and genuine. Bluesky's dev community dislikes marketing speak. No hashtags needed.",
    },
    "mastodon": {
        "limit": 500,
        "style": "Friendly and substantive. 1-3 relevant hashtags (e.g. #OpenSource) are welcome on Mastodon.",
    },
    "discord": {
        "limit": 2000,
        "style": "Announcement for the project's own Discord. Markdown allowed. Warm, community tone.",
    },
    "telegram": {
        "limit": 4000,
        "style": "Channel announcement. Plain text, short paragraphs.",
    },
    "linkedin": {
        "limit": 3000,
        "style": (
            "Professional but human — no buzzword salad. A strong first line (it's the "
            "hook before 'see more'), then short paragraphs and a clear takeaway. "
            "1-3 relevant hashtags at the end are fine."
        ),
    },
    "reddit": {
        "limit": 6000,
        "style": (
            "A Reddit post: first line is the title, then a blank line, then the body. "
            "Redditors reward honesty and technical depth and destroy anything that smells like an ad. "
            "Explain what the project does, why it exists, and invite feedback."
        ),
    },
}


def _chat(cfg: dict, system: str, user: str) -> str:
    ocfg = cfg["ollama"]
    url = ocfg["base_url"].rstrip("/") + "/api/chat"
    headers = {}
    api_key = env("OLLAMA_API_KEY")
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    payload = {
        "model": ocfg["model"],
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "stream": False,
        "options": {"temperature": ocfg.get("temperature", 0.7)},
    }
    r = requests.post(url, json=payload, headers=headers, timeout=300)
    r.raise_for_status()
    content = r.json()["message"]["content"]
    # Reasoning models may emit <think> blocks; drop them.
    content = re.sub(r"<think>.*?</think>", "", content, flags=re.S)
    return content.strip().strip('"')


def _system_prompt(cfg: dict) -> str:
    p = cfg["project"]
    return (
        f"You write social media posts promoting {p['name']}, an open-source GitHub project. "
        f"About the project: {p['pitch'].strip()} "
        f"Project link: {p['homepage']}. "
        "Rules: never invent features, numbers, or praise that is not in the provided material. "
        "Always include the project link. Output ONLY the post text, nothing else."
    )


def _showcase_framing(item: dict) -> str:
    if not item.get("strength"):
        return ""
    frame = (
        "\nThis is a SHOWCASE: nyx actually executed this just now. Lead with the fact "
        "that nyx *did* it autonomously — show, don't tell. Do not invent tickers, "
        "returns, percentages, or metrics beyond what is in the material.\n"
    )
    if "no_return_promise" in item.get("guardrails", []):
        frame += (
            "CRITICAL: never promise or imply guaranteed/risk-free returns or profits, "
            "and do not present any figure as investment advice. The angle is the "
            "autonomous process and constitutional governance, not performance.\n"
        )
    return frame


def generate_post(cfg: dict, platform: str, item: dict) -> str:
    spec = PLATFORM_SPECS[platform]
    user = (
        f"Platform: {platform}. Hard limit: {spec['limit']} characters. Style: {spec['style']}\n\n"
        f"Write one post about this {item['kind']}:\n"
        f"Title: {item['title']}\n"
        f"Material:\n{item['context']}\n"
        f"{_showcase_framing(item)}"
    )
    if item.get("url"):
        user += f"Link to include: {item['url']}\n"

    text = _chat(cfg, _system_prompt(cfg), user)
    if len(text) > spec["limit"]:
        text = _chat(
            cfg,
            _system_prompt(cfg),
            user + f"\nYour previous draft was {len(text)} characters — too long. "
            f"Rewrite it under {spec['limit']} characters:\n{text}",
        )
    if len(text) > spec["limit"]:
        text = text[: spec["limit"] - 1] + "…"
    return text


def generate_thread(cfg: dict, platform: str, item: dict, max_posts: int = 4) -> list[str]:
    """Turn a rich item into a short reply-chain thread (reach lever for X/Bluesky).

    Returns a list of posts, each within the platform limit. The first is a
    scroll-stopping hook; the last carries the call to action + link.
    """
    spec = PLATFORM_SPECS[platform]
    user = (
        f"Platform: {platform}. Write a thread of 2-{max_posts} posts, each STRICTLY "
        f"under {spec['limit']} characters. Style: {spec['style']}\n"
        "Post 1: a scroll-stopping hook (no link, no 'a thread 🧵' cliché). "
        "Middle posts: the concrete substance from the material. "
        "Final post: a clear call to action (star / try the repo) WITH the link.\n"
        "Separate posts with a line containing only '---'. Output only the posts.\n\n"
        f"About this {item['kind']}:\nTitle: {item['title']}\nMaterial:\n{item['context']}\n"
        f"{_showcase_framing(item)}"
        f"Link (final post only): {item.get('url', cfg['project']['homepage'])}\n"
    )
    text = _chat(cfg, _system_prompt(cfg), user)
    parts = [p.strip() for p in re.split(r"(?m)^\s*-{3,}\s*$", text) if p.strip()]
    posts = []
    for i, p in enumerate(parts[:max_posts]):
        if len(p) > spec["limit"]:
            p = p[: spec["limit"] - 1] + "…"
        posts.append(p)
    # Guarantee the link survives in the final post.
    link = item.get("url", cfg["project"]["homepage"])
    if posts and link not in posts[-1] and len(posts[-1]) + len(link) + 1 <= spec["limit"]:
        posts[-1] = f"{posts[-1]} {link}"
    return posts or [generate_post(cfg, platform, item)]


def generate_article(cfg: dict, item: dict) -> tuple[str, str]:
    """Long-form markdown article for dev.to. Returns (title, body_markdown)."""
    user = (
        "Write a dev.to blog post (markdown) about the material below. "
        "400-800 words, honest developer tone, code-block examples only if they appear in the material. "
        "First line must be the title prefixed with 'TITLE: ', then the markdown body.\n\n"
        f"Kind: {item['kind']}\nTitle: {item['title']}\nMaterial:\n{item['context']}\n"
        f"Link the project: {item.get('url', cfg['project']['homepage'])}\n"
    )
    text = _chat(cfg, _system_prompt(cfg), user)
    lines = text.split("\n", 1)
    title = lines[0].replace("TITLE:", "").strip().lstrip("# ").strip()
    body = lines[1].strip() if len(lines) > 1 else text
    return title, body
