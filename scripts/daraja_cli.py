#!/usr/bin/env python3
"""Daraja CLI — quick access to Daraja, tests, and pipeline utilities.

Usage:
    daraja check                            # health check
    daraja auth                             # verify OAuth token
    daraja stk <phone> <amount>             # fire STK Push
    daraja status <ref>                     # show a transaction
    daraja tx [<ref>]                       # list transactions
    daraja test [group]                     # run test_daraja.py
    daraja contacts                         # list contacts
    daraja sheng <text>                     # test Sheng normalizer
    daraja env                              # show current config
    daraja trace-c2b [--text "..."]         # trace C2B end-to-end
    daraja trace-b2c [--phone ...] [--amount N]  # trace B2C end-to-end
    daraja trace-wiring                     # trace full C2C wiring
"""

import argparse
import json
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

TX_DIR = PROJECT_ROOT / "data" / "transactions"
SERVER = "http://localhost:8000"
MOCK   = "http://localhost:8765"


def _http(method, url, body=None, timeout=10):
    data = json.dumps(body).encode() if body is not None else None
    headers = {"Content-Type": "application/json"}
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            raw = r.read().decode()
            return r.status, json.loads(raw) if raw else {}
    except urllib.error.HTTPError as e:
        return e.code, {"error": e.read().decode()[:200]}
    except Exception as e:
        return 0, {"error": str(e)}


def _print_json(obj):
    print(json.dumps(obj, indent=2, ensure_ascii=False))


# ------------------------------------------------------------------
# Commands
# ------------------------------------------------------------------

def cmd_check(_):
    from src.daraja import BASE_URL, SHORTCODE
    print(f"BASE_URL:  {BASE_URL}")
    print(f"SHORTCODE: {SHORTCODE}")
    print()
    code, _ = _http("GET", f"{MOCK}/health")
    print(f"mock:    {'✓ up' if code == 200 else f'✗ down (HTTP {code})'}")
    code, _ = _http("GET", f"{SERVER}/")
    print(f"server:  {'✓ up' if code == 200 else f'✗ down (HTTP {code})'}")


def cmd_auth(_):
    from src.daraja import get_access_token, _token_cache, BASE_URL
    _token_cache["token"] = None
    _token_cache["expires_at"] = 0
    print(f"Auth endpoint: {BASE_URL}")
    try:
        t = get_access_token()
        print(f"✓ token: {t[:25]}... ({len(t)} chars)")
    except Exception as e:
        print(f"✗ auth failed: {e}")
        return 1
    return 0


def cmd_stk(args):
    from src.daraja import stk_push, BASE_URL
    print(f"POST {BASE_URL}/mpesa/stkpush/v1/processrequest")
    r = stk_push(
        phone=args.phone,
        amount=args.amount,
        callback_url="https://example.com/cb",
        account_ref="CLI",
    )
    _print_json(r)


def cmd_status(args):
    p = TX_DIR / f"{args.ref}.json"
    if not p.exists():
        print(f"✗ no transaction file: {p}")
        return 1
    _print_json(json.loads(p.read_text()))


def cmd_tx(args):
    if args.ref:
        return cmd_status(args)
    if not TX_DIR.exists():
        print("(no transactions directory)")
        return 0
    files = sorted(TX_DIR.glob("*.json"), key=lambda f: f.stat().st_mtime, reverse=True)
    print(f"{len(files)} transactions (newest first):\n")
    for f in files[:20]:
        try:
            tx = json.loads(f.read_text())
        except Exception:
            continue
        ref    = tx.get("ref") or f.stem
        intent = tx.get("intent") or "?"
        status = tx.get("status") or "?"
        amount = tx.get("amount", tx.get("slots", {}).get("amount", "?"))
        print(f"  {str(ref):35s}  {str(intent):20s}  {str(amount):>8s}  [{status}]")


def cmd_test(args):
    cmd = [sys.executable, str(PROJECT_ROOT / "scripts" / "test_daraja.py")]
    if args.group:
        cmd.append(args.group)
    return subprocess.run(cmd).returncode


def cmd_contacts(_):
    from src.contacts import all_contacts
    c = all_contacts()
    print(f"{len(c)} contacts:\n")
    for name, phone in sorted(c.items()):
        print(f"  {name:15s}  {phone}")


def cmd_sheng(args):
    from src.sheng_normalize import normalize_sheng, extract_amounts
    text = " ".join(args.text)
    print(f"in:  {text!r}")
    print(f"out: {normalize_sheng(text)!r}")
    print(f"amt: {extract_amounts(normalize_sheng(text))}")


def cmd_env(_):
    from src.daraja import BASE_URL, SHORTCODE, CONSUMER_KEY, PASSKEY
    print(f"BASE_URL:  {BASE_URL}")
    print(f"SHORTCODE: {SHORTCODE}")
    print(f"KEY ends:  ...{CONSUMER_KEY[-8:]}")
    print(f"PASSKEY ends: ...{PASSKEY[-8:]}")


def cmd_trace_c2b(args):
    cmd = [sys.executable, str(PROJECT_ROOT / "scripts" / "trace_c2b.py")]
    if args.text:
        cmd += ["--text", args.text]
    return subprocess.run(cmd).returncode


def cmd_trace_b2c(args):
    cmd = [sys.executable, str(PROJECT_ROOT / "scripts" / "trace_b2c.py")]
    if args.phone:
        cmd += ["--phone", args.phone]
    if args.amount:
        cmd += ["--amount", str(args.amount)]
    return subprocess.run(cmd).returncode


def cmd_trace_wiring(_):
    return subprocess.run([sys.executable,
                            str(PROJECT_ROOT / "scripts" / "trace_wiring.py")]).returncode


# ------------------------------------------------------------------
# Parser
# ------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(prog="daraja")
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("check").set_defaults(fn=cmd_check)
    sub.add_parser("auth").set_defaults(fn=cmd_auth)
    sub.add_parser("env").set_defaults(fn=cmd_env)
    sub.add_parser("contacts").set_defaults(fn=cmd_contacts)
    sub.add_parser("trace-wiring").set_defaults(fn=cmd_trace_wiring)

    p = sub.add_parser("stk")
    p.add_argument("phone")
    p.add_argument("amount", type=float)
    p.set_defaults(fn=cmd_stk)

    p = sub.add_parser("status")
    p.add_argument("ref")
    p.set_defaults(fn=cmd_status)

    p = sub.add_parser("tx")
    p.add_argument("ref", nargs="?", default=None)
    p.set_defaults(fn=cmd_tx)

    p = sub.add_parser("test")
    p.add_argument("group", nargs="?", default=None)
    p.set_defaults(fn=cmd_test)

    p = sub.add_parser("sheng")
    p.add_argument("text", nargs="+")
    p.set_defaults(fn=cmd_sheng)

    p = sub.add_parser("trace-c2b")
    p.add_argument("--text", default=None)
    p.set_defaults(fn=cmd_trace_c2b)

    p = sub.add_parser("trace-b2c")
    p.add_argument("--phone", default=None)
    p.add_argument("--amount", type=int, default=None)
    p.set_defaults(fn=cmd_trace_b2c)

    args = parser.parse_args()
    sys.exit(args.fn(args) or 0)


if __name__ == "__main__":
    main()
