#!/usr/bin/env python3
"""Trace every hop of a C2B (STK Push) request.

Usage:
    python scripts/trace_c2b.py                     # default: send 100 to john
    python scripts/trace_c2b.py --text "tuma 500 kwa mary"
    python scripts/trace_c2b.py --amount 250 --name john
"""

import argparse
import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

SERVER = "http://localhost:8000"
MOCK   = "http://localhost:8765"
TX_DIR = PROJECT_ROOT / "data" / "transactions"


def http(method, url, body=None, timeout=15):
    data = json.dumps(body).encode() if body is not None else None
    headers = {}
    if data is not None:
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            raw = r.read().decode()
            return r.status, json.loads(raw) if raw else {}, time.time() - t0
    except urllib.error.HTTPError as e:
        body = ""
        try:
            body = e.read().decode()[:200]
        except Exception:
            pass
        return e.code, {"error": body or e.reason}, time.time() - t0
    except Exception as e:
        return 0, {"error": str(e)}, time.time() - t0


def hr(label):
    print(f"\n{'=' * 62}")
    print(f"  {label}")
    print('=' * 62)


def show(label, data, dt=None):
    timing = f"  ({dt*1000:.0f} ms)" if dt is not None else ""
    print(f"\n── {label}{timing}")
    print(json.dumps(data, indent=2, ensure_ascii=False)[:1200])


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--text", default=None, help="Raw command text")
    p.add_argument("--amount", type=int, default=100)
    p.add_argument("--name", default="john")
    args = p.parse_args()

    text = args.text or f"send {args.amount} to {args.name}"

    hr(f"C2B TRACE — {text!r}")

    # --- 1. Health check ---
    hr("STEP 1 — health")
    code, _, dt = http("GET", f"{MOCK}/health")
    print(f"  mock:    HTTP {code}  ({dt*1000:.0f} ms)")
    code, _, dt = http("GET", f"{SERVER}/")
    print(f"  server:  HTTP {code}  ({dt*1000:.0f} ms)")

    # --- 2. Frontend → /command ---
    hr("STEP 2 — frontend → server:  POST /command")
    code, r1, dt = http("POST", f"{SERVER}/command", {"text": text})
    print(f"  status: {code}  ({dt*1000:.0f} ms)")
    if code != 200:
        print(f"  ✗ pipeline failed: {r1}")
        return 1
    print(f"  intent:        {r1.get('intent')!r}")
    print(f"  slots:         {r1.get('slots')}")
    print(f"  resolved phone:{r1.get('phone')!r}")
    print(f"  ussd_menu:     {r1.get('ussd_menu')!r}")

    run_id = r1["run_id"]

    # --- 3. Frontend → /demo/send-money (fires STK Push) ---
    hr("STEP 3 — frontend → server:  POST /demo/send-money  →  Daraja")
    code, r2, dt = http("POST", f"{SERVER}/demo/send-money", {
        "amount": args.amount,
        "phone": "254708374149",
        "recipient": args.name,
        "ref": run_id,
        "intent": r1.get("intent", "SEND_MONEY"),
    })
    print(f"  status: {code}  ({dt*1000:.0f} ms)")
    print(f"  body:")
    print(json.dumps(r2, indent=2, ensure_ascii=False)[:800])
    ref = r2.get("ref", run_id)

    # --- 4. Transaction state ---
    hr(f"STEP 4 — transaction file:  data/transactions/{ref}.json")
    tx_path = TX_DIR / f"{ref}.json"
    if tx_path.exists():
        tx = json.loads(tx_path.read_text())
        print(f"  intent:               {tx.get('intent')}")
        print(f"  status:               {tx.get('status')}")
        print(f"  checkout_request_id:  {tx.get('checkout_request_id')}")
        print(f"  phone:                {tx.get('phone')}")
        print(f"  amount:               {tx.get('amount')}")
    else:
        print(f"  ✗ no transaction file")
        return 1

    # --- 5. Simulate the Leg 1 callback ---
    hr("STEP 5 — Safaricom → server:  POST /daraja/c2b-result")
    code, r3, dt = http("POST", f"{SERVER}/daraja/c2b-result?ref={ref}", {
        "Body": {"stkCallback": {
            "ResultCode": 0,
            "ResultDesc": "The service request is processed successfully.",
            "CheckoutRequestID": "ws_CO_TRACE_001",
            "CallbackMetadata": {"Item": [
                {"Name": "MpesaReceiptNumber", "Value": "TRACE001"},
                {"Name": "Amount", "Value": args.amount},
                {"Name": "PhoneNumber", "Value": 254708374149},
            ]},
        }}
    })
    print(f"  status: {code}  ({dt*1000:.0f} ms)")

    time.sleep(2)

    # --- 6. Final state ---
    hr("STEP 6 — final transaction state")
    tx = json.loads(tx_path.read_text())
    print(f"  status:      {tx.get('status')}")
    print(f"  last_callback:")
    print(json.dumps(tx.get("last_callback", {}), indent=2))

    # --- 7. Status endpoint ---
    hr("STEP 7 — frontend polls:  GET /daraja/status/<ref>")
    code, r4, dt = http("GET", f"{SERVER}/daraja/status/{ref}")
    print(f"  status: {code}  ({dt*1000:.0f} ms)")
    print(f"  body:   {r4}")

    hr("C2B TRACE COMPLETE")
    return 0


if __name__ == "__main__":
    sys.exit(main())
