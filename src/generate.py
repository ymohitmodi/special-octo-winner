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


def generate_post(cfg: dict, platform: str, item: dict) -> str:
    spec = PLATFORM_SPECS[platform]
    user = (
        f"Platform: {platform}. Hard limit: {spec['limit']} characters. Style: {spec['style']}\n\n"
        f"Write one post about this {item['kind']}:\n"
        f"Title: {item['title']}\n"
        f"Material:\n{item['context']}\n"
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
