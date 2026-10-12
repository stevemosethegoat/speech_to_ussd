"""Pending action store.

A "pending action" is a payment or menu selection that the user has been
asked to confirm. Keyed by run_id (the same ID used for traces).

Lifecycle:
    1. run_pipeline() writes a pending action after showing the USSD menu.
    2. confirm_and_execute(run_id, "yes"|"no") reads it and either fires
       the payment or discards it.
"""

import json
from datetime import datetime, timezone
from pathlib import Path

PENDING_DIR = Path("data/pending")
PENDING_DIR.mkdir(parents=True, exist_ok=True)

# Expire pending actions after 10 minutes — avoids stale confirmations
TTL_SECONDS = 600


def save_pending(run_id: str, intent: str, slots: dict, menu: str,
                 ussd_sequence: str = "") -> Path:
    payload = {
        "run_id": run_id,
        "intent": intent,
        "slots": slots,
        "menu": menu,
        "ussd_sequence": ussd_sequence,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    path = PENDING_DIR / f"{run_id}.json"
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False))
    return path


def load_pending(run_id: str) -> dict | None:
    path = PENDING_DIR / f"{run_id}.json"
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text())
    except json.JSONDecodeError:
        return None

    # Expiry check
    created = data.get("created_at")
    if created:
        try:
            age = (datetime.now(timezone.utc)
                   - datetime.fromisoformat(created)).total_seconds()
            if age > TTL_SECONDS:
                path.unlink(missing_ok=True)
                return None
        except ValueError:
            pass

    return data


def clear_pending(run_id: str) -> None:
    (PENDING_DIR / f"{run_id}.json").unlink(missing_ok=True)


def list_pending() -> list[dict]:
    out = []
    for p in sorted(PENDING_DIR.glob("*.json")):
        try:
            out.append(json.loads(p.read_text()))
        except json.JSONDecodeError:
            continue
    return out
