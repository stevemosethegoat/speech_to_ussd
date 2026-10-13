"""In-memory + JSON-file transaction store for the C2C two-leg flow.

Keyed by reference (== run_id). Updated by Safaricom callbacks.
"""

import json
from datetime import datetime, timezone
from pathlib import Path

TX_DIR = Path("data/transactions")
TX_DIR.mkdir(parents=True, exist_ok=True)


def _path(ref: str) -> Path:
    return TX_DIR / f"{ref}.json"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def get(ref: str) -> dict | None:
    p = _path(ref)
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text())
    except json.JSONDecodeError:
        return None


def put(ref: str, data: dict) -> None:
    payload = dict(data)
    payload.setdefault("ref", ref)
    payload.setdefault("created_at", _now())
    payload["updated_at"] = _now()
    _path(ref).write_text(json.dumps(payload, indent=2, ensure_ascii=False))


def update(ref: str, **fields) -> None:
    tx = get(ref) or {"ref": ref}
    tx.update(fields)
    tx["updated_at"] = _now()
    _path(ref).write_text(json.dumps(tx, indent=2, ensure_ascii=False))


def list_all() -> list[dict]:
    out = []
    for p in sorted(TX_DIR.glob("*.json")):
        try:
            out.append(json.loads(p.read_text()))
        except json.JSONDecodeError:
            continue
    return out
