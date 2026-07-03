"""Persistent state: what has already been posted, and daily rate accounting."""
import json
from datetime import date, datetime
from pathlib import Path

STATE_FILE = Path(__file__).resolve().parent.parent / "state.json"


class State:
    def __init__(self, data: dict):
        self.data = data

    @classmethod
    def load(cls) -> "State":
        if STATE_FILE.exists():
            with open(STATE_FILE, encoding="utf-8") as f:
                return cls(json.load(f))
        return cls({"published": {}, "post_log": []})

    def save(self) -> None:
        with open(STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(self.data, f, indent=2)

    def already_done(self, item_id: str, platform: str) -> bool:
        return platform in self.data["published"].get(item_id, [])

    def mark_done(self, item_id: str, platform: str) -> None:
        self.data["published"].setdefault(item_id, []).append(platform)

    def record_auto_post(self) -> None:
        self.data["post_log"].append(datetime.now().isoformat())

    def auto_posts_today(self) -> int:
        today = date.today().isoformat()
        return sum(1 for t in self.data["post_log"] if t.startswith(today))
