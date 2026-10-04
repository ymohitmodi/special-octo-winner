"""The nyx → promoter contract for auto-generated content.

nyx runs autonomously and produces deliverables (a shipped feature summary, a
market note, a research digest, a blog post…). Rather than teaching the promoter
about each one, nyx just drops a marketing-ready *artifact* into an outbox
directory, and the promoter markets whatever it finds — no code changes per
content type.

An artifact is one piece of content to promote. Supported files in the outbox:

  * ``*.json``  — one artifact object, or a JSON list of them.
  * ``*.md`` / ``*.txt`` — body is the content; optional YAML frontmatter carries
    metadata. With no frontmatter, the title is the first ``# heading`` (or the
    filename) and the whole body is the material.

Artifact fields (all optional except ``context``/body):

  id         stable unique id; dedupe key. Defaults to ``outbox:<relpath>``.
  kind       what it is, e.g. "market note" (used in the generation prompt).
  title      short title.
  context    the auto-generated content / material the post is written from.
  url        link to include; defaults to the project homepage.
  strength   tag as a nyx strength ("software"/"investing"/"advisor"/…); enables
             showcase framing and thread eligibility.
  guardrails list of guardrail names, e.g. ["no_return_promise"].
  platforms  restrict to these platforms (subset of the enabled ones).
  thread     bool; override the global thread setting for this item.
"""
from __future__ import annotations

from pathlib import Path
from typing import Iterable

import yaml

ARTIFACT_GLOBS = ("*.json", "*.md", "*.txt", "*.markdown")


def _split_frontmatter(raw: str) -> tuple[dict, str]:
    """Return (metadata, body). Supports a leading ``---`` YAML block."""
    if raw.startswith("---"):
        end = raw.find("\n---", 3)
        if end != -1:
            meta = yaml.safe_load(raw[3:end]) or {}
            body = raw[end + 4:].lstrip("\n")
            if isinstance(meta, dict):
                return meta, body
    return {}, raw


def _first_heading(body: str, fallback: str) -> str:
    for line in body.splitlines():
        s = line.strip()
        if s.startswith("#"):
            return s.lstrip("#").strip()
        if s:
            return s[:120]
    return fallback


def _normalize(obj: dict, cfg: dict, default_id: str) -> dict | None:
    context = (obj.get("context") or obj.get("body") or "").strip()
    if not context:
        return None
    return {
        "id": str(obj.get("id") or default_id),
        "kind": obj.get("kind", "update"),
        "title": obj.get("title") or _first_heading(context, obj.get("kind", "nyx update")),
        "context": context[:8000],
        "url": obj.get("url") or cfg["project"]["homepage"],
        "strength": obj.get("strength"),
        "guardrails": obj.get("guardrails") or [],
        "platforms": obj.get("platforms"),
        "thread": obj.get("thread"),
        "_source_file": obj.get("_source_file"),
    }


def read_artifacts(directory: str | Path, cfg: dict) -> list[dict]:
    """Discover and normalize every artifact in the outbox directory."""
    base = Path(directory).expanduser()
    if not base.is_dir():
        return []
    items: list[dict] = []
    seen_files: set[Path] = set()
    for pattern in ARTIFACT_GLOBS:
        for path in sorted(base.rglob(pattern)):
            if path in seen_files or "published" in path.parts:
                continue
            seen_files.add(path)
            rel = path.relative_to(base).as_posix()
            raw = path.read_text(encoding="utf-8", errors="replace")
            if path.suffix == ".json":
                import json

                try:
                    data = json.loads(raw)
                except json.JSONDecodeError:
                    continue
                objs = data if isinstance(data, list) else [data]
                for i, obj in enumerate(objs):
                    if not isinstance(obj, dict):
                        continue
                    obj["_source_file"] = str(path)
                    norm = _normalize(obj, cfg, default_id=f"outbox:{rel}#{i}")
                    if norm:
                        items.append(norm)
            else:
                meta, body = _split_frontmatter(raw)
                meta = {**meta, "body": body, "_source_file": str(path)}
                norm = _normalize(meta, cfg, default_id=f"outbox:{rel}")
                if norm:
                    items.append(norm)
    return items


def archive(item: dict, archive_dir: str | Path) -> None:
    """Move a processed artifact's source file under ``archive_dir``.

    Only single-artifact files are moved (a multi-artifact JSON list may still
    have unpublished siblings, so those are left in place and deduped by state).
    """
    src = item.get("_source_file")
    if not src:
        return
    src_path = Path(src)
    if not src_path.exists() or "#" in item["id"]:
        return
    dest_dir = Path(archive_dir).expanduser()
    dest_dir.mkdir(parents=True, exist_ok=True)
    src_path.replace(dest_dir / src_path.name)


# --- producer helper: nyx (or any tool) can import this to emit an artifact ---

def write_artifact(
    outbox_dir: str | Path,
    *,
    context: str,
    title: str | None = None,
    kind: str = "update",
    url: str | None = None,
    strength: str | None = None,
    guardrails: Iterable[str] | None = None,
    platforms: Iterable[str] | None = None,
    thread: bool | None = None,
    artifact_id: str | None = None,
) -> Path:
    """Write one marketing-ready artifact into the outbox as JSON.

    Import from nyx's own code to auto-publish its output, e.g.::

        from outbox import write_artifact
        write_artifact(OUTBOX, kind="market note", title=headline,
                       context=analysis_text, strength="investing",
                       guardrails=["no_return_promise"])
    """
    import json
    import time

    base = Path(outbox_dir).expanduser()
    base.mkdir(parents=True, exist_ok=True)
    obj = {k: v for k, v in {
        "id": artifact_id,
        "kind": kind,
        "title": title,
        "context": context,
        "url": url,
        "strength": strength,
        "guardrails": list(guardrails) if guardrails else None,
        "platforms": list(platforms) if platforms else None,
        "thread": thread,
    }.items() if v is not None}
    stamp = artifact_id or f"{kind.replace(' ', '-')}-{int(time.time() * 1000)}"
    safe = "".join(c if c.isalnum() or c in "-_" else "-" for c in stamp)[:80]
    path = base / f"{safe}.json"
    path.write_text(json.dumps(obj, indent=2), encoding="utf-8")
    return path
