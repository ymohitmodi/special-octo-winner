"""Load config.yaml + .env into one settings object."""
import os
from pathlib import Path

import yaml
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent


def load_config() -> dict:
    load_dotenv(ROOT / ".env")
    with open(ROOT / "config.yaml", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    return cfg


def env(name: str, required: bool = False) -> str:
    val = os.getenv(name, "").strip()
    if required and not val:
        raise RuntimeError(f"Missing required environment variable {name} (set it in .env)")
    return val
