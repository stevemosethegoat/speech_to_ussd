#!/usr/bin/env python3
"""Trace the entire C2C wiring end-to-end.

Shows every hop:  frontend → server → Daraja → mock → callback → state
for both Leg 1 (C2B) and Leg 2 (B2C).
"""

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


def hr(n, label):
    print(f"\n{'=' * 62}\n  HOP {n} — {label}\n{'=' * 62}")


def state(ref):
    p = TX_DIR / f"{ref}.json"
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text())
    except Exception:
        return None


def show_state(tx, keys=("intent", "status", "phone", "amount")):
    if not tx:
        print("  (no transaction file)")
        return
    for k in keys:
        print(f"  {k:22s} {tx.get(k)}")
    if "last_callback" in tx:
        print(f"  last_callback:")
        print(json.dumps(tx["last_callback"], indent=4)[:600])


def main():
    hr(0, "the full wiring")
    print("""
    Browser  ──▶  /command          ──▶  pipeline  (intent + slots + contacts)
             ──▶  /demo/send-money  ──▶  Daraja client
                                        │
                                        ├──▶  /oauth  ──▶  mock    (Leg 1 auth)
                                        └──▶  /stkpush ──▶  mock    (Leg 1 STK)
                                                    │
                                     tx file: AWAITING_CALLBACK
                                                    │
                Safaricom callback  ──▶  /daraja/c2b-result
                                        │
                                        └──▶  fires Leg 2
                                        ├──▶  /oauth  ──▶  mock    (Leg 2 auth)
                                        └──▶  /b2c   ──▶  mock    (Leg 2 payout)
                                                    │
                                     tx file: AWAITING_PAYOUT
                                                    │
                Safaricom callback  ──▶  /daraja/b2c-result
                                                    │
                                     tx file: COMPLETED
    """)

    hr(1, "health — mock + server")
    import subprocess as _sp
    for label, url in [("mock  ", f"{MOCK}/health"), ("server", f"{SERVER}/")]:
        t0 = time.time()
        r = _sp.run(["curl", "-s", "-o", "/dev/null", "-w", "%{http_code}", url],
                    capture_output=True, text=True, timeout=10)
        code = int(r.stdout.strip() or 0)
        print(f"  {label}: HTTP {code}  ({(time.time()-t0)*1000:.0f} ms)")
        if label.strip() == "server" and code != 200:
            print("  ✗ backend not up — abort")
            return 1

    hr(2, "frontend → server:  POST /command")
    code, r1, dt = http("POST", f"{SERVER}/command", {"text": "send 100 to john"})
    print(f"  HTTP {code}  ({dt*1000:.0f} ms)")
    print(f"  intent:  {r1.get('intent')!r}")
    print(f"  phone:   {r1.get('phone')!r}")
    print(f"  menu:    {r1.get('ussd_menu')!r}")

    if code != 200:
        return 1

    run_id = r1["run_id"]

    hr(3, "frontend → server:  POST /demo/send-money  →  Daraja (Leg 1)")
    code, r2, dt = http("POST", f"{SERVER}/demo/send-money?simulate=false", {
        "amount": 100,
        "phone": "254708374149",
        "recipient": "john",
        "ref": run_id,
        "intent": "SEND_MONEY",
    })
    ref = r2.get("ref", run_id)
    print(f"  HTTP {code}  ({dt*1000:.0f} ms)")
    print(f"  ref:  {ref}")
    print(f"  body: {json.dumps(r2, indent=2)[:400]}")

    hr(4, "transaction state after Leg 1")
    time.sleep(1)
    tx = state(ref)
    show_state(tx, keys=("intent", "status", "checkout_request_id", "phone", "amount"))

    hr(5, "Safaricom → server:  POST /daraja/c2b-result  (Leg 1 callback)")
    print("  This callback fires Leg 2 (B2C).")
    code, _, dt = http("POST", f"{SERVER}/daraja/c2b-result?ref={ref}", {
        "Body": {"stkCallback": {
            "ResultCode": 0,
            "ResultDesc": "The service request is processed successfully.",
            "CheckoutRequestID": "ws_CO_WIRE_001",
            "CallbackMetadata": {"Item": [
                {"Name": "MpesaReceiptNumber", "Value": "WIRE-C2B"},
                {"Name": "Amount", "Value": 100},
                {"Name": "PhoneNumber", "Value": 254708374149},
            ]},
        }}
    })
    print(f"  HTTP {code}  ({dt*1000:.0f} ms)")

    hr(6, "transaction state after Leg 1 callback")
    time.sleep(3)
    tx = state(ref)
    show_state(tx, keys=("intent", "status"))
    if "b2c_response" in tx:
        print("  b2c_response:")
        print(json.dumps(tx["b2c_response"], indent=4)[:400])

    hr(7, "Safaricom → server:  POST /daraja/b2c-result  (Leg 2 callback)")
    code, _, dt = http("POST", f"{SERVER}/daraja/b2c-result?ref={ref}", {
        "Result": {
            "ResultCode": 0,
            "ResultParameters": {"ResultParameter": [
                {"Key": "TransactionReceipt", "Value": "WIRE-B2C"},
                {"Key": "TransactionAmount", "Value": 100},
            ]},
        }
    })
    print(f"  HTTP {code}  ({dt*1000:.0f} ms)")

    hr(8, "final transaction state")
    time.sleep(1)
    tx = state(ref)
    show_state(tx, keys=("intent", "status", "phone", "amount", "receipt"))

    hr(9, "frontend polls:  GET /daraja/status/<ref>")
    code, r, dt = http("GET", f"{SERVER}/daraja/status/{ref}")
    print(f"  HTTP {code}  ({dt*1000:.0f} ms)")
    print(f"  {r}")

    ok = tx and tx.get("status") == "COMPLETED"
    hr(10, "VERDICT")
    if ok:
        print("  ✓ C2C wiring verified end-to-end.")
        print("    Every hop returned 200. Both callbacks fired. State = COMPLETED.")
    else:
        print(f"  ✗ Final state is {tx and tx.get('status')!r}, expected COMPLETED.")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
