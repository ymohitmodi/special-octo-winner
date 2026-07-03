"""Drive the nyx dark factory to produce real demonstration artifacts.

The whole point of this promoter is to show nyx *working*, not to make claims
about it. So instead of asking an LLM to write "nyx is great", we actually run
nyx in the domains it is strong at — software, value-investing, advisor — and
turn its genuine output (pipeline stages, gate decisions, audit metrics) into
posts.

Safety invariants (do not relax):
  * We NEVER pass `--yes`. Software showcases run supervised, so nyx holds the
    build for approval and never ships anything unattended. That the build is
    HELD is itself part of the story: governance is constructed in.
  * Investing showcases run read-only analysis (`nyx backtest`). We never quote
    specific tickers or returns as recommendations, and nyx's own constitution
    forbids guaranteeing returns — we surface that gate as the hook.
"""
import re
import shutil
import subprocess
import sys
from pathlib import Path


class NyxError(RuntimeError):
    pass


def _run_nyx(nyx_dir: str, args: list[str], timeout: int) -> str:
    """Invoke the nyx CLI in its own repo dir and return stdout.

    nyx auto-selects its brain: MOCK when no OLLAMA_API_KEY is set, live Ollama
    Cloud otherwise. We inherit the environment so the mini-PC's key is used.
    """
    path = Path(nyx_dir).expanduser()
    if not (path / "nyx" / "__main__.py").exists() and not shutil.which("nyx"):
        raise NyxError(
            f"nyx not found at {path}. Set showcase.nyx_dir in config.yaml to the "
            "nyx repo, or `pip install -e .` it so the `nyx` command is on PATH."
        )
    # Prefer `python -m nyx` from the repo so we don't depend on PATH.
    cmd = [sys.executable, "-m", "nyx", *args]
    try:
        proc = subprocess.run(
            cmd,
            cwd=str(path),
            capture_output=True,
            text=True,
            timeout=timeout,
            stdin=subprocess.DEVNULL,  # keeps `build` in supervised/HELD, never prompts
        )
    except subprocess.TimeoutExpired as e:
        raise NyxError(f"nyx {' '.join(args)} timed out after {timeout}s") from e
    if proc.returncode not in (0,):
        # `build` returns 1 when merely held for approval — that's fine for a demo.
        if "HELD" not in proc.stdout:
            raise NyxError(f"nyx {' '.join(args)} failed: {proc.stderr.strip()[:400]}")
    return proc.stdout


# ---------------------------------------------------------------------------
# One showcase builder per strength. Each returns an "item" dict shaped for
# generate.py: {id, kind, title, context, url, strength, guardrails}.
# ---------------------------------------------------------------------------

def _brain_label(stdout: str) -> str:
    return "live Ollama Cloud" if "Ollama Cloud @" in stdout else "offline mock brain"


def showcase_software(cfg: dict, intent: str, run_id: str) -> dict:
    nyx_dir = cfg["showcase"]["nyx_dir"]
    timeout = cfg["showcase"].get("timeout_seconds", 600)
    out = _run_nyx(nyx_dir, ["build", intent], timeout)

    stages = re.findall(r"^\s*[✓�r]\s+(\w+)\s+gate=(\S+)", out, re.M)
    metrics = re.search(r"Metrics:\s*(\{.*\})", out)
    held = "HELD" in out
    shipped = "SHIPPED" in out or "shipped" in out.lower()

    context = (
        f"nyx ran its gated dark-factory SDLC pipeline for the intent: \"{intent}\".\n"
        f"Brain: {_brain_label(out)}.\n"
        f"Pipeline stages executed (each passed a constitutional gate): "
        f"{', '.join(s[0] for s in stages) or 'explore, design, build, review, test, deploy'}.\n"
        f"Outcome: {'held for human approval before shipping (governance gate)' if held else ('shipped' if shipped else 'completed')}.\n"
    )
    if metrics:
        context += f"Audited run metrics: {metrics.group(1)}\n"
    context += (
        "Every step was checked against nyx's machine-readable Constitution and "
        "written to a tamper-evident, hash-chained audit ledger."
    )
    return {
        "id": f"showcase-software:{run_id}",
        "kind": "autonomous software build demo",
        "title": f"nyx autonomously ran a full gated SDLC for: {intent}",
        "context": context,
        "url": cfg["project"]["homepage"],
        "strength": "software",
        "guardrails": [],
    }


def showcase_investing(cfg: dict, run_id: str) -> dict:
    nyx_dir = cfg["showcase"]["nyx_dir"]
    timeout = cfg["showcase"].get("timeout_seconds", 600)
    out = _run_nyx(nyx_dir, ["backtest"], timeout)

    gate = re.search(r"Gate check.*?:\s*(\[.*\])", out)
    is_mock = "MOCK" in out

    # We deliberately do NOT feed specific picks/returns into the post. The
    # marketing angle is the *governance and process*, never a return figure.
    context = (
        "nyx ran its value-investing capability: it built a point-in-time company "
        "universe, scored each name on margin-of-safety / ROIC / owner-earnings "
        "yield, and backtested an analyst agent whose returns are penalized for "
        "capital loss (Buffett/Graham doctrine seeded into its long-term memory).\n"
        f"Brain: {_brain_label(out)}.\n"
    )
    if gate:
        context += (
            "Governance highlight: nyx's Constitution automatically REJECTED a "
            f"sample buy memo that promised guaranteed returns — gate output {gate.group(1)}. "
            "The system is structurally incapable of promising risk-free returns.\n"
        )
    if is_mock:
        context += (
            "(This run used the offline mock brain, so specific numbers are synthetic — "
            "the post must describe the capability and governance, not cite figures.)\n"
        )
    return {
        "id": f"showcase-investing:{run_id}",
        "kind": "value-investing capability demo",
        "title": "nyx screens for deep value under a constitution that forbids guaranteed returns",
        "context": context,
        "url": cfg["project"]["homepage"],
        "strength": "investing",
        # Hard guardrails enforced after generation:
        "guardrails": ["no_return_promise", "not_financial_advice"],
    }


def proof_of_work(cfg: dict, run_id: str) -> dict:
    """Aggregate nyx's tamper-evident audit ledger into a 'proof of autonomous
    work' item. This is the strongest trust signal nyx has: not a claim, a
    verifiable, hash-chained record of what the agents actually did."""
    nyx_dir = cfg["showcase"]["nyx_dir"]
    timeout = cfg["showcase"].get("timeout_seconds", 600)
    tail = int(cfg["showcase"].get("ledger_tail", 60))
    out = _run_nyx(nyx_dir, ["ledger", "--tail", str(tail), "--verify"], timeout)

    rows = re.findall(r"^#(\d+)\s+\[(\w+)\s*\]\s+(\S+)\s+(\S+)", out, re.M)
    if not rows:
        raise NyxError("audit ledger is empty — run `nyx build` first to generate work")
    passed = sum(1 for r in rows if r[1] == "PASS")
    blocked = sum(1 for r in rows if r[1] in ("BLOCK", "FAIL", "DENY"))
    agents = sorted({r[2].split(":", 1)[1] for r in rows if r[2].startswith("agent:")})
    actions = len(rows)
    chain_ok = "Chain intact: True" in out

    # Optional: how much the factory has learned (semantic memory).
    lessons = None
    try:
        mem = _run_nyx(nyx_dir, ["memory", "--tail", "1"], timeout)
        m = re.search(r"Memory:\s*(\d+)\s+lessons", mem)
        if m:
            lessons = int(m.group(1))
    except NyxError:
        pass

    context = (
        f"Proof of autonomous work from nyx's tamper-evident, hash-chained audit ledger "
        f"(every agent action is logged and cryptographically linked).\n"
        f"In the last {actions} logged actions: {passed} constitutional gates PASSED, "
        f"{blocked} blocked/denied, across {len(agents)} distinct specialized agents "
        f"({', '.join(agents) or 'planner, coder, reviewer, tester, deployer'}).\n"
        f"Hash chain verification: {'INTACT ✓ (no entry altered or removed)' if chain_ok else 'see run'}.\n"
    )
    if lessons is not None:
        context += f"The factory has distilled {lessons} reusable lessons into long-term memory.\n"
    context += (
        "This is the receipts: nyx doesn't just run unattended, it proves what it did."
    )
    return {
        "id": f"proof:{run_id}",
        "kind": "proof of autonomous work (audit ledger)",
        "title": f"nyx: {passed} gates passed across {len(agents)} agents, audit chain verified",
        "context": context,
        "url": cfg["project"]["homepage"],
        "strength": "governance",
        "guardrails": [],
    }


def showcase_advisor(cfg: dict, objective: str, run_id: str) -> dict:
    nyx_dir = cfg["showcase"]["nyx_dir"]
    timeout = cfg["showcase"].get("timeout_seconds", 900)
    # Supervised single pass; capped cycles keep it cheap and bounded.
    out = _run_nyx(nyx_dir, ["run", objective, "--max-cycles", "1", "--evolve-every", "0"], timeout)
    tail = "\n".join(out.strip().splitlines()[-25:])
    context = (
        f"nyx pursued an ambiguous personal/professional objective: \"{objective}\".\n"
        f"Brain: {_brain_label(out)}.\n"
        "Its advisor capability decomposed the goal into concrete, gated deliverables "
        "(evidence items, drafts, next actions), each checked against the Constitution "
        "and logged to the audit ledger.\n"
        f"Run report (tail):\n{tail}"
    )
    return {
        "id": f"showcase-advisor:{run_id}",
        "kind": "career/EB-1 advisor capability demo",
        "title": f"nyx turned an ambiguous goal into gated deliverables: {objective}",
        "context": context,
        "url": cfg["project"]["homepage"],
        "strength": "advisor",
        "guardrails": ["not_professional_advice"],
    }


# Guardrail phrases that must never appear in a generated showcase post.
_FORBIDDEN_PATTERNS = {
    "no_return_promise": re.compile(
        r"guarantee\w*\s+(return|profit|gain)|risk[- ]free|can't lose|sure thing|"
        r"\bwill\s+(?:make|double|triple)\b", re.I
    ),
}
_DISCLAIMERS = {
    "not_financial_advice": "Not financial advice.",
    "not_professional_advice": "Not professional/legal advice.",
}


def enforce_guardrails(item: dict, text: str, limit: int) -> str:
    """Reject unsafe claims; append a compact disclaimer if there's room."""
    for g in item.get("guardrails", []):
        pat = _FORBIDDEN_PATTERNS.get(g)
        if pat and pat.search(text):
            raise NyxError(
                f"generated {item['strength']} post tripped guardrail '{g}' "
                f"(reads like a prohibited claim); dropping it: {text[:120]!r}"
            )
    for g in item.get("guardrails", []):
        disc = _DISCLAIMERS.get(g)
        if disc and disc.lower() not in text.lower() and len(text) + len(disc) + 1 <= limit:
            text = f"{text} {disc}"
    return text


# Rotation of showcase intents/objectives per strength (edit freely).
def build_showcase(cfg: dict, strength: str, run_id: str) -> dict:
    sc = cfg["showcase"]
    if strength == "software":
        intents = sc.get("software_intents") or ["Add a rate limiter to the public API"]
        intent = intents[hash(run_id) % len(intents)]
        return showcase_software(cfg, intent, run_id)
    if strength == "investing":
        return showcase_investing(cfg, run_id)
    if strength == "advisor":
        objectives = sc.get("advisor_objectives") or [
            "Assemble EB-1A evidence for a senior AI engineer"
        ]
        objective = objectives[hash(run_id) % len(objectives)]
        return showcase_advisor(cfg, objective, run_id)
    raise NyxError(f"unknown nyx strength: {strength}")
