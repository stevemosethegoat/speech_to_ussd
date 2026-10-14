#!/usr/bin/env python3
"""Trace every hop of a B2C (payout) request."""

import argparse
import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

MOCK = "http://localhost:8765"


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


def hr(l):
    print(f"\n{'=' * 62}\n  {l}\n{'=' * 62}")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--phone", default="254712345678")
    p.add_argument("--amount", type=int, default=1)
    args = p.parse_args()

    hr(f"B2C TRACE — pay {args.amount} to {args.phone}")

    hr("STEP 1 — health")
    code, _, dt = http("GET", f"{MOCK}/health")
    print(f"  mock: HTTP {code}  ({dt*1000:.0f} ms)")

    hr("STEP 2 — server → Daraja:  POST /mpesa/b2c/v3/paymentrequest")
    from src.daraja import b2c_payment, BASE_URL, INITIATOR_NAME, SECURITY_CREDENTIAL
    print(f"  BASE_URL:              {BASE_URL}")
    print(f"  INITIATOR_NAME:        {INITIATOR_NAME!r}")
    print(f"  SECURITY_CREDENTIAL:   {'(set, ' + str(len(SECURITY_CREDENTIAL)) + ' chars)' if SECURITY_CREDENTIAL else '(EMPTY!)'}")

    t0 = time.time()
    r = b2c_payment(
        phone=args.phone,
        amount=args.amount,
        result_url="http://localhost:8000/daraja/b2c-result",
        timeout_url="http://localhost:8000/daraja/timeout",
        remarks="B2C Trace",
    )
    dt = time.time() - t0

    print(f"\n  took: {dt*1000:.0f} ms")
    print(f"  response:")
    print(json.dumps(r, indent=2, ensure_ascii=False)[:1000])

    hr("B2C TRACE COMPLETE")
    return 0 if "ResponseCode" in r and str(r["ResponseCode"]) == "0" else 1


if __name__ == "__main__":
    sys.exit(main())
