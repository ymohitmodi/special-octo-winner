# The nyx outbox: auto-marketing nyx's auto-generated content

nyx runs autonomously and produces deliverables all the time — a shipped
feature, a market note, a research digest, a career-evidence draft. The **outbox**
is a generic hand-off: nyx drops a marketing-ready *artifact* into a directory,
and the promoter markets whatever it finds. New content types need **zero code**
in the promoter.

```
   nyx (autonomous)                     nyx-promoter (daily)
   ─────────────────                    ────────────────────
   produces output ──▶ nyx_outbox/*.{json,md,txt} ──▶ read → generate → publish
                                                        │
                                                        └▶ archive to published/
```

## Where

Default directory: `nyx_outbox/` (set `nyx_outbox.dir` in `config.yaml`). You can
register several outboxes via the `sources:` list — e.g. one per nyx capability.

## Artifact formats

**JSON** — one object, or a list of objects:

```json
{
  "id": "feature-billing-2026-07",
  "kind": "shipped feature",
  "title": "nyx shipped a billing dashboard, end to end",
  "context": "The full material the post is written from …",
  "strength": "software",
  "platforms": ["x", "bluesky", "linkedin"]
}
```

**Markdown / text** — body is the content; optional YAML frontmatter adds metadata:

```markdown
---
kind: market note
title: This week's value screen
strength: investing
guardrails: [no_return_promise, not_financial_advice]
thread: true
---
The auto-generated content goes here …
```

With no frontmatter, the title is the first `# heading` (or filename) and the
whole body becomes the material.

## Fields

| Field | Required | Meaning |
|-------|----------|---------|
| `context` / body | ✅ | The auto-generated content the post is written from |
| `id` | — | Stable dedupe key. Defaults to `outbox:<relpath>` |
| `kind` | — | What it is (used in the prompt), e.g. `"market note"` |
| `title` | — | Short title |
| `url` | — | Link to include (defaults to the project homepage) |
| `strength` | — | `software` / `investing` / `advisor` / … — enables showcase framing and threads |
| `guardrails` | — | e.g. `["no_return_promise", "not_financial_advice"]` |
| `platforms` | — | Restrict to a subset of enabled platforms |
| `thread` | — | `true`/`false` to force/suppress threading for this item |

## Emitting artifacts from nyx

Any nyx code can import the producer helper:

```python
from outbox import write_artifact

write_artifact(
    "nyx_outbox",
    kind="market note",
    title=headline,
    context=analysis_text,
    strength="investing",
    guardrails=["no_return_promise", "not_financial_advice"],
    platforms=["bluesky", "linkedin"],
)
```

That's the whole integration: nyx writes, the promoter markets. Guardrails are
enforced on the generated post (a `no_return_promise` artifact can never produce
a "guaranteed returns" post), and each artifact is published once per platform,
then archived to `nyx_outbox/published/`.
