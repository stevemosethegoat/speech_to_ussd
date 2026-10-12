"""Contact name -> phone number lookup for the payment pipeline.

Reads contacts.json from data/ (preferred) or src/ (fallback).
Used for DISPLAY ONLY — the STK Push always targets
DARAJA_FIXED_PHONE from .env.
"""

import json
from pathlib import Path

_MODULE_DIR = Path(__file__).resolve().parent
_CANDIDATES = [
    _MODULE_DIR.parent / "data" / "contacts.json",   # data/contacts.json
    _MODULE_DIR / "contacts.json",                    # src/contacts.json
]

def _resolve() -> Path:
    for c in _CANDIDATES:
        if c.exists():
            return c
    return _CANDIDATES[0]   # default

CONTACTS_FILE = _resolve()


def _load() -> dict:
    if not CONTACTS_FILE.exists():
        return {}
    try:
        data = json.loads(CONTACTS_FILE.read_text())
    except json.JSONDecodeError:
        return {}
    return {str(k).strip().lower(): str(v).strip() for k, v in data.items()}


def lookup_contact(name: str) -> str | None:
    """Return the phone number for a name, or None."""
    if not name:
        return None
    query = name.strip().lower()
    contacts = _load()
    if query in contacts:
        return contacts[query]
    first = query.split()[0]
    if first in contacts:
        return contacts[first]
    for k, v in contacts.items():
        if k in query or query in k:
            return v
    return None


def all_contacts() -> dict:
    return _load()
