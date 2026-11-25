# SPDX-License-Identifier: Apache-2.0
"""Declared equivalent mutants.

An equivalent mutant changes the code without changing any observable
behaviour (e.g. sorting a list that is always built in order): no test can
kill it, and asking for a "killer test" only burns effort. Equivalence is a
judgement — TestBoost never decides it alone: the agent or a human declares
it, with a reason, through `testboost equivalent`.

Declarations live at project level (`.testboost/equivalents.json`): they
describe the code, not a session. A mutant is identified by a hash of its
class, method, line, mutator and description, so when the code moves the id
changes and the mutant comes back as an ordinary survivor (the safe default).
"""

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

FICHIER = "equivalents.json"
MIN_REASON_LENGTH = 10


def mutant_id(mutant: dict[str, Any]) -> str:
    """Stable 10-hex id of a PIT mutant (identical mutants on one line share it)."""
    key = "|".join(str(mutant.get(k, "")) for k in ("class", "method", "line", "mutator", "description"))
    return hashlib.sha1(key.encode("utf-8")).hexdigest()[:10]


def with_ids(mutants: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [{**m, "id": m.get("id") or mutant_id(m)} for m in mutants]


def _path(project_path: str) -> Path:
    return Path(project_path) / ".testboost" / FICHIER


def load(project_path: str) -> dict[str, dict[str, Any]]:
    """Declared equivalents by mutant id."""
    path = _path(project_path)
    if not path.exists():
        return {}
    return {e["id"]: e for e in json.loads(path.read_text(encoding="utf-8"))}


def _save(project_path: str, declared: dict[str, dict[str, Any]]) -> None:
    path = _path(project_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    entries = sorted(declared.values(), key=lambda e: (e["class"], e["line"], e["id"]))
    path.write_text(json.dumps(entries, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def declare(project_path: str, survivors: list[dict[str, Any]], ids: list[str], reason: str) -> list[dict]:
    """Declare surviving mutants equivalent. Raises ValueError on an unknown id or a missing reason."""
    reason = (reason or "").strip()
    if len(reason) < MIN_REASON_LENGTH:
        raise ValueError(
            f"A reason is required (at least {MIN_REASON_LENGTH} characters): why can no test "
            "observe this mutant?")
    by_id = {m["id"]: m for m in with_ids(survivors)}
    unknown = [i for i in ids if i not in by_id]
    if unknown:
        raise ValueError(f"Not a surviving mutant of the last `mutate` run: {', '.join(unknown)}")
    declared = load(project_path)
    now = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    added = []
    for i in ids:
        m = by_id[i]
        entry = {"id": i, "class": m["class"], "method": m["method"], "line": m["line"],
                 "mutator": m["mutator"], "description": m["description"], "reason": reason,
                 "declared_at": now}
        declared[i] = entry
        added.append(entry)
    _save(project_path, declared)
    return added


def remove(project_path: str, ids: list[str]) -> list[str]:
    """Withdraw declarations; returns the ids that were declared."""
    declared = load(project_path)
    removed = [i for i in ids if declared.pop(i, None) is not None]
    _save(project_path, declared)
    return removed


def split(project_path: str, survivors: list[dict[str, Any]]) -> tuple[list[dict], list[dict]]:
    """(real survivors, declared equivalents) — each mutant carries its id."""
    declared = load(project_path)
    real, equivalent = [], []
    for m in with_ids(survivors):
        if m["id"] in declared:
            equivalent.append({**m, "reason": declared[m["id"]]["reason"]})
        else:
            real.append(m)
    return real, equivalent


def effective_score(mutations: dict[str, int], equivalent_count: int) -> float:
    """Mutation score once declared equivalents are taken out of the denominator
    (PIT's convention, like the raw score: killed and timed-out mutants are detected)."""
    detected = mutations.get("killed", 0) + mutations.get("timed_out", 0)
    total = mutations.get("total", 0) - equivalent_count
    return round(100.0 * detected / total, 1) if total > 0 else 100.0
