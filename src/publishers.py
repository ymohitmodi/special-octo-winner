"""One publish function per platform, all via official APIs."""
import re
from datetime import datetime, timezone

import requests
from requests_oauthlib import OAuth1

from config import env

TIMEOUT = 30


def publish_bluesky(pcfg: dict, text: str, item: dict) -> str:
    handle = env("BLUESKY_HANDLE", required=True)
    password = env("BLUESKY_APP_PASSWORD", required=True)
    session = requests.post(
        "https://bsky.social/xrpc/com.atproto.server.createSession",
        json={"identifier": handle, "password": password},
        timeout=TIMEOUT,
    )
    session.raise_for_status()
    auth = session.json()

    # Bluesky needs byte-offset "facets" for links to be clickable.
    facets = []
    raw = text.encode("utf-8")
    for m in re.finditer(rb"https?://[^\s]+", raw):
        facets.append({
            "index": {"byteStart": m.start(), "byteEnd": m.end()},
            "features": [{
                "$type": "app.bsky.richtext.facet#link",
                "uri": m.group().decode("utf-8"),
            }],
        })

    record = {
        "$type": "app.bsky.feed.post",
        "text": text,
        "createdAt": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    }
    if facets:
        record["facets"] = facets
    r = requests.post(
        "https://bsky.social/xrpc/com.atproto.repo.createRecord",
        headers={"Authorization": f"Bearer {auth['accessJwt']}"},
        json={"repo": auth["did"], "collection": "app.bsky.feed.post", "record": record},
        timeout=TIMEOUT,
    )
    r.raise_for_status()
    return r.json().get("uri", "posted")


def publish_mastodon(pcfg: dict, text: str, item: dict) -> str:
    token = env("MASTODON_ACCESS_TOKEN", required=True)
    base = pcfg.get("base_url", "https://mastodon.social").rstrip("/")
    r = requests.post(
        f"{base}/api/v1/statuses",
        headers={"Authorization": f"Bearer {token}"},
        json={"status": text, "visibility": "public"},
        timeout=TIMEOUT,
    )
    r.raise_for_status()
    return r.json().get("url", "posted")


def publish_devto(pcfg: dict, text: str, item: dict) -> str:
    """`text` here is 'TITLE\\n\\nbody_markdown' assembled by main."""
    api_key = env("DEVTO_API_KEY", required=True)
    title, _, body = text.partition("\n\n")
    r = requests.post(
        "https://dev.to/api/articles",
        headers={"api-key": api_key},
        json={"article": {
            "title": title.strip(),
            "body_markdown": body.strip(),
            "published": True,
            "tags": pcfg.get("tags", ["opensource"])[:4],
        }},
        timeout=TIMEOUT,
    )
    r.raise_for_status()
    return r.json().get("url", "posted")


def publish_discord(pcfg: dict, text: str, item: dict) -> str:
    webhook = env("DISCORD_WEBHOOK_URL", required=True)
    r = requests.post(webhook, json={"content": text}, timeout=TIMEOUT)
    r.raise_for_status()
    return "posted"


def publish_telegram(pcfg: dict, text: str, item: dict) -> str:
    token = env("TELEGRAM_BOT_TOKEN", required=True)
    chat_id = env("TELEGRAM_CHAT_ID", required=True)
    r = requests.post(
        f"https://api.telegram.org/bot{token}/sendMessage",
        json={"chat_id": chat_id, "text": text},
        timeout=TIMEOUT,
    )
    r.raise_for_status()
    return "posted"


def publish_x(pcfg: dict, text: str, item: dict) -> str:
    auth = OAuth1(
        env("X_CONSUMER_KEY", required=True),
        env("X_CONSUMER_SECRET", required=True),
        env("X_ACCESS_TOKEN", required=True),
        env("X_ACCESS_TOKEN_SECRET", required=True),
    )
    r = requests.post(
        "https://api.twitter.com/2/tweets",
        json={"text": text},
        auth=auth,
        timeout=TIMEOUT,
    )
    r.raise_for_status()
    tweet_id = r.json().get("data", {}).get("id", "")
    return f"https://x.com/i/status/{tweet_id}" if tweet_id else "posted"


def publish_reddit(pcfg: dict, text: str, item: dict) -> str:
    raise RuntimeError(
        "Reddit is draft-only by design: automated self-promotion violates most "
        "subreddit rules and gets accounts banned. Set mode: draft in config.yaml."
    )


PUBLISHERS = {
    "bluesky": publish_bluesky,
    "mastodon": publish_mastodon,
    "devto": publish_devto,
    "discord": publish_discord,
    "telegram": publish_telegram,
    "x": publish_x,
    "reddit": publish_reddit,
}
