"""Dispatch a pipeline result to the appropriate Daraja flow.

Maps intents to Daraja operations:
    SEND_MONEY  -> initiate_c2c_transfer (or b2c_payment)
    PAY_BILL    -> stk_push
    BUY_GOODS   -> stk_push
    BUY_AIRTIME -> stk_push
    WITHDRAW    -> b2c_payment
    DEPOSIT     -> stk_push
    CHECK_BALANCE -> not a payment (returns info)

Currently stubbed — logs the intended route and returns a placeholder.
Replace each branch with a real call once B2C credentials are set up.
"""

from datetime import datetime, timezone


PAYMENT_INTENTS = {
    "SEND_MONEY", "PAY_BILL", "BUY_GOODS",
    "BUY_AIRTIME", "WITHDRAW", "DEPOSIT",
}


def dispatch_to_daraja(result: dict) -> dict:
    """Route a completed pipeline result to the correct Daraja API call.

    Args:
        result: the dict returned by run_pipeline() — contains
                intent, slots, run_id, etc.

    Returns:
        dict describing the attempted/simulated Daraja action.
    """
    intent = result.get("intent", "")
    slots = result.get("slots", {})
    run_id = result.get("run_id", "")

    base = {
        "intent": intent,
        "run_id": run_id,
        "slots": slots,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    if intent not in PAYMENT_INTENTS:
        return {**base, "status": "skipped",
                "reason": f"{intent} is not a payment intent"}

    amount = slots.get("amount") or ""
    if not amount:
        return {**base, "status": "skipped",
                "reason": "no amount in slots"}

    # Real dispatches go here. For now, return a dry-run descriptor.
    try:
        from src.daraja import (
            stk_push, b2c_payment,
            initiate_c2c_transfer,
        )
    except ImportError as exc:
        return {**base, "status": "error",
                "error": f"could not import daraja: {exc}"}

    # Placeholder — log what would happen without firing a live request.
    return {
        **base,
        "status": "stub_not_executed",
        "note": ("dispatch_to_daraja is a stub. "
                 "Uncomment the branch below to fire a real request."),
        # Example of what SEND_MONEY would look like once B2C creds exist:
        # "would_call": "initiate_c2c_transfer",
        # "recipient": slots.get("recipient"),
    }


def describe_routes() -> dict:
    """Return the intent -> Daraja mapping for documentation."""
    return {
        "SEND_MONEY":   "initiate_c2c_transfer (needs B2C creds)",
        "PAY_BILL":     "stk_push",
        "BUY_GOODS":    "stk_push",
        "BUY_AIRTIME":  "stk_push",
        "WITHDRAW":     "b2c_payment (needs B2C creds)",
        "DEPOSIT":      "stk_push",
        "CHECK_BALANCE": "account balance API (needs B2C creds)",
    }
