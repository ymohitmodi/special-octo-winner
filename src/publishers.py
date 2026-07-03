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


def publish_bluesky_thread(pcfg: dict, posts: list[str], item: dict) -> str:
    """Post a reply-chain thread. Returns the root post's URI."""
    handle = env("BLUESKY_HANDLE", required=True)
    password = env("BLUESKY_APP_PASSWORD", required=True)
    session = requests.post(
        "https://bsky.social/xrpc/com.atproto.server.createSession",
        json={"identifier": handle, "password": password},
        timeout=TIMEOUT,
    )
    session.raise_for_status()
    auth = session.json()
    headers = {"Authorization": f"Bearer {auth['accessJwt']}"}

    def _facets(text: str):
        facets = []
        raw = text.encode("utf-8")
        for m in re.finditer(rb"https?://[^\s]+", raw):
            facets.append({
                "index": {"byteStart": m.start(), "byteEnd": m.end()},
                "features": [{"$type": "app.bsky.richtext.facet#link",
                              "uri": m.group().decode("utf-8")}],
            })
        return facets

    root = None  # {"uri","cid"}
    parent = None
    for text in posts:
        record = {
            "$type": "app.bsky.feed.post",
            "text": text,
            "createdAt": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        }
        f = _facets(text)
        if f:
            record["facets"] = f
        if root and parent:
            record["reply"] = {"root": root, "parent": parent}
        r = requests.post(
            "https://bsky.social/xrpc/com.atproto.repo.createRecord",
            headers=headers,
            json={"repo": auth["did"], "collection": "app.bsky.feed.post", "record": record},
            timeout=TIMEOUT,
        )
        r.raise_for_status()
        ref = {"uri": r.json()["uri"], "cid": r.json()["cid"]}
        parent = ref
        if root is None:
            root = ref
    return root["uri"] if root else "posted"


def publish_x_thread(pcfg: dict, posts: list[str], item: dict) -> str:
    auth = OAuth1(
        env("X_CONSUMER_KEY", required=True),
        env("X_CONSUMER_SECRET", required=True),
        env("X_ACCESS_TOKEN", required=True),
        env("X_ACCESS_TOKEN_SECRET", required=True),
    )
    prev_id = None
    first_id = None
    for text in posts:
        payload = {"text": text}
        if prev_id:
            payload["reply"] = {"in_reply_to_tweet_id": prev_id}
        r = requests.post("https://api.twitter.com/2/tweets", json=payload,
                          auth=auth, timeout=TIMEOUT)
        r.raise_for_status()
        prev_id = r.json().get("data", {}).get("id", "")
        first_id = first_id or prev_id
    return f"https://x.com/i/status/{first_id}" if first_id else "posted"


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

# Platforms that support native reply-chain threads (a reach multiplier).
THREAD_PUBLISHERS = {
    "bluesky": publish_bluesky_thread,
    "x": publish_x_thread,
}
