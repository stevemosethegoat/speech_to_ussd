#!/usr/bin/env python3
"""Test harness for Daraja API code.

Usage:
    python scripts/test_daraja.py                 # run all cases
    python scripts/test_daraja.py stk_push        # run one group
    python scripts/test_daraja.py --list          # list case names
    python scripts/test_daraja.py --live          # hit real Safaricom (not mock)

By default this hits whatever DARAJA_BASE_URL points at in .env.
Point it at daraja-mock (http://127.0.0.1:8765) for offline tests.
"""

import argparse
import json
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

CASES_PATH = PROJECT_ROOT / "tests" / "daraja" / "cases.json"


def load_cases(path: Path = CASES_PATH) -> dict:
    if not path.exists():
        print(f"cases file not found: {path}")
        sys.exit(1)
    return json.loads(path.read_text())


# ------------------------------------------------------------------
# Individual test groups
# ------------------------------------------------------------------

def test_auth(case: dict) -> tuple[bool, str]:
    from src.daraja import get_access_token
    from src.daraja import _token_cache
    # Force a fresh call so we actually hit the endpoint
    _token_cache["token"] = None
    _token_cache["expires_at"] = 0
    try:
        token = get_access_token()
        ok = bool(token) and len(token) > 10
        return ok, f"token: {token[:20]}... ({len(token)} chars)"
    except Exception as e:
        return False, f"exception: {e}"


def test_stk_push(case: dict) -> tuple[bool, str]:
    from src.daraja import stk_push
    inp = case["input"]
    expect = case.get("expect", {})
    try:
        r = stk_push(
            phone=inp["phone"],
            amount=inp["amount"],
            callback_url="https://example.com/cb",
            account_ref=inp.get("account_ref", "TEST"),
        )
        # Success expectation
        if "ResponseCode" in expect:
            ok = str(r.get("ResponseCode")) == expect["ResponseCode"]
            return ok, f"ResponseCode={r.get('ResponseCode')!r}  id={r.get('CheckoutRequestID')}"
        # Error expectation
        if expect.get("error"):
            ok = "errorCode" in r or "error" in r
            return ok, f"got error response: {json.dumps(r)[:120]}"
        # Ambiguous
        return True, f"response: {json.dumps(r)[:120]}"
    except Exception as e:
        if expect.get("error") or expect.get("error_or_normalized"):
            return True, f"raised (expected): {e}"
        return False, f"exception: {e}"


TEST_GROUPS = {
    "auth":     test_auth,
    "stk_push": test_stk_push,
}


# ------------------------------------------------------------------
# Runner
# ------------------------------------------------------------------

def run_group(group_name: str, cases: dict) -> tuple[int, int, list[str]]:
    if group_name not in TEST_GROUPS:
        return 0, 0, [f"unknown group: {group_name}"]

    fn = TEST_GROUPS[group_name]
    group_cases = cases.get(group_name, [])
    passed, failed = 0, 0
    lines = []

    print(f"\n=== {group_name} ({len(group_cases)} cases) ===")
    for i, case in enumerate(group_cases, 1):
        name = case.get("name", f"case {i}")
        t0 = time.time()
        try:
            ok, detail = fn(case)
        except Exception as e:
            ok, detail = False, f"harness exception: {e}"
        dt = time.time() - t0

        icon = "✓" if ok else "✗"
        print(f"  {icon} [{i}/{len(group_cases)}] {name}  ({dt:.2f}s)")
        print(f"      {detail}")

        if ok:
            passed += 1
        else:
            failed += 1

    return passed, failed, lines


def main():
    parser = argparse.ArgumentParser(description="Daraja test harness")
    parser.add_argument("group", nargs="?", help="test group name (default: all)")
    parser.add_argument("--list", action="store_true", help="list all case names")
    args = parser.parse_args()

    cases = load_cases()

    if args.list:
        for group, items in cases.items():
            print(f"{group}:")
            for i, c in enumerate(items, 1):
                print(f"  [{i}] {c.get('name', 'unnamed')}")
        return

    groups = [args.group] if args.group else list(cases.keys())

    # Show which base URL we'll hit
    from src.daraja import BASE_URL, SHORTCODE
    print(f"DARAJA_BASE_URL: {BASE_URL}")
    print(f"SHORTCODE:       {SHORTCODE}")

    total_p = total_f = 0
    for g in groups:
        p, f, _ = run_group(g, cases)
        total_p += p
        total_f += f

    print(f"\n{'=' * 50}")
    print(f"TOTAL: {total_p} passed, {total_f} failed")
    print(f"{'=' * 50}")

    sys.exit(0 if total_f == 0 else 1)


if __name__ == "__main__":
    main()
