"""Daraja API client.

Handles two transaction shapes used by this project:

  - Direct B2C: Withdraw Cash, Loan Disbursement, and any other intent where
    the business account pays a customer directly. One leg, one callback.

  - C2C (via chaining): Send Money. Daraja has no public peer-to-peer API,
    so a "customer to customer" transfer is simulated as two legs:
        Leg 1 (C2B / STK Push): sender pays this app's business shortcode
        Leg 2 (B2C)            : this app's business account pays the recipient
    Leg 2 only fires after Leg 1's callback confirms success.

Direct C2B intents (Pay Bill, Buy Goods, Buy Airtime, Savings Deposit) also
go through stk_push()/c2b_simulate() below, but are single-leg — no B2C
follow-up — handled by whoever dispatches on intent in server.py.
"""

import base64
import time
from datetime import datetime

import requests
from requests.auth import HTTPBasicAuth

# --- Config -----------------------------------------------------------
# Load these from environment variables in real use (python-dotenv);
# left as plain constants here for clarity.

CONSUMER_KEY = "0A0mrNBgHT6n3VsPUQHlH7xzjpKxlAvZ7jx4Z3CCsQGG15XA"
CONSUMER_SECRET = "UVDQgQhFXeTLN1BOadG3oQpiLliRBGvffw9DAJsQQ1CX9r4HZmnZRZC6oix19FyJ"

SHORTCODE = "174379"          # sandbox STK Push shortcode
PASSKEY = "bfb279f9aa9bdbcf158e97dd71a467cd2e0c893059b10f78e6b72ada1ed2c919"      # from Daraja portal > Lipa Na M-Pesa > Simulate

INITIATOR_NAME = "testapi"           # B2C initiator (sandbox default)
SECURITY_CREDENTIAL = "YOUR_SECURITY_CREDENTIAL"  # encrypted initiator password

BASE_URL = "https://sandbox.safaricom.co.ke"       # swap for api.safaricom.co.ke in prod
PUBLIC_BASE_URL = "https://YOUR-NGROK-URL.ngrok-free.app"  # update per ngrok session


# --- OAuth token, cached until near expiry -----------------------------

_token_cache = {"token": None, "expires_at": 0}


def get_access_token() -> str:
    if _token_cache["token"] and time.time() < _token_cache["expires_at"]:
        return _token_cache["token"]

    resp = requests.get(
        f"{BASE_URL}/oauth/v1/generate?grant_type=client_credentials",
        auth=HTTPBasicAuth(CONSUMER_KEY, CONSUMER_SECRET),
        timeout=15,
    )
    resp.raise_for_status()
    data = resp.json()

    _token_cache["token"] = data["access_token"]
    _token_cache["expires_at"] = time.time() + 3500  # a little under 1hr
    return _token_cache["token"]


def _auth_header() -> dict:
    return {"Authorization": f"Bearer {get_access_token()}"}


# --- C2B (used for direct C2B intents, and as Leg 1 of a C2C transfer) --

def stk_push(phone: str, amount: float, callback_url: str,
             account_ref: str = "VoiceUSSD", description: str = "Payment") -> dict:
    """Sends an STK Push prompt to `phone`. Safaricom calls callback_url
    once the customer enters their PIN (or cancels / times out)."""

    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    password = base64.b64encode(
        f"{SHORTCODE}{PASSKEY}{timestamp}".encode()
    ).decode()

    payload = {
        "BusinessShortCode": SHORTCODE,
        "Password": password,
        "Timestamp": timestamp,
        "TransactionType": "CustomerPayBillOnline",
        "Amount": int(amount),
        "PartyA": phone,
        "PartyB": SHORTCODE,
        "PhoneNumber": phone,
        "CallBackURL": callback_url,
        "AccountReference": account_ref,
        "TransactionDesc": description,
    }

    resp = requests.post(
        f"{BASE_URL}/mpesa/stkpush/v1/processrequest",
        json=payload, headers=_auth_header(), timeout=15,
    )
    return resp.json()


def register_c2b_urls(validation_url: str, confirmation_url: str,
                       response_type: str = "Completed") -> dict:
    """One-time setup per shortcode — not called per-transaction."""
    payload = {
        "ShortCode": SHORTCODE,
        "ResponseType": response_type,
        "ConfirmationURL": confirmation_url,
        "ValidationURL": validation_url,
    }
    resp = requests.post(
        f"{BASE_URL}/mpesa/c2b/v1/registerurl",
        json=payload, headers=_auth_header(), timeout=15,
    )
    return resp.json()


# --- B2C (direct Withdraw/Loan intents, and Leg 2 of a C2C transfer) ---

def b2c_payment(phone: str, amount: float, result_url: str, timeout_url: str,
                 command_id: str = "BusinessPayment",
                 remarks: str = "Payout") -> dict:
    """Disburses money from the business account to `phone`."""

    payload = {
        "InitiatorName": INITIATOR_NAME,
        "SecurityCredential": SECURITY_CREDENTIAL,
        "CommandID": command_id,          # BusinessPayment | SalaryPayment | PromotionPayment
        "Amount": int(amount),
        "PartyA": SHORTCODE,
        "PartyB": phone,
        "Remarks": remarks,
        "QueueTimeOutURL": timeout_url,
        "ResultURL": result_url,
        "Occasion": "VoiceUSSD",
    }

    resp = requests.post(
        f"{BASE_URL}/mpesa/b2c/v1/paymentrequest",
        json=payload, headers=_auth_header(), timeout=15,
    )
    return resp.json()


# --- TSQ: fallback when a callback hasn't arrived in time ---------------

def transaction_status_query(transaction_id: str, party_a: str,
                              result_url: str, timeout_url: str,
                              identifier_type: str = "4") -> dict:
    payload = {
        "Initiator": INITIATOR_NAME,
        "SecurityCredential": SECURITY_CREDENTIAL,
        "CommandID": "TransactionStatusQuery",
        "TransactionID": transaction_id,
        "PartyA": party_a,
        "IdentifierType": identifier_type,   # 4 = shortcode
        "ResultURL": result_url,
        "QueueTimeOutURL": timeout_url,
        "Remarks": "Status check",
        "Occasion": "VoiceUSSD",
    }
    resp = requests.post(
        f"{BASE_URL}/mpesa/transactionstatus/v1/query",
        json=payload, headers=_auth_header(), timeout=15,
    )
    return resp.json()


# --- High-level helpers tying intents to the right flow -----------------

def initiate_c2c_transfer(sender_phone: str, recipient_phone: str,
                           amount: float, reference: str) -> dict:
    """Kicks off Leg 1 (C2B) of a simulated C2C "Send Money" transfer.
    Leg 2 (B2C) is triggered separately, from the C2B callback handler,
    once this leg is confirmed — see server.py's _daraja_c2b_callback."""

    callback_url = f"{PUBLIC_BASE_URL}/daraja/c2b-result?ref={reference}"
    return stk_push(
        phone=sender_phone,
        amount=amount,
        callback_url=callback_url,
        account_ref=reference,
        description="Send money (leg 1 of 2)",
    )


def continue_c2c_transfer(recipient_phone: str, amount: float, reference: str) -> dict:
    """Kicks off Leg 2 (B2C) after Leg 1 succeeded."""

    result_url = f"{PUBLIC_BASE_URL}/daraja/b2c-result?ref={reference}"
    timeout_url = f"{PUBLIC_BASE_URL}/daraja/timeout?ref={reference}"
    return b2c_payment(
        phone=recipient_phone,
        amount=amount,
        result_url=result_url,
        timeout_url=timeout_url,
        remarks="Send money (leg 2 of 2)",
    )


def initiate_direct_b2c(phone: str, amount: float, reference: str,
                         command_id: str = "BusinessPayment") -> dict:
    """For intents that are genuinely single-leg B2C: Withdraw Cash,
    Loan Disbursement. No C2B leg involved."""

    result_url = f"{PUBLIC_BASE_URL}/daraja/b2c-result?ref={reference}"
    timeout_url = f"{PUBLIC_BASE_URL}/daraja/timeout?ref={reference}"
    return b2c_payment(
        phone=phone, amount=amount,
        result_url=result_url, timeout_url=timeout_url,
        command_id=command_id,
    )


def initiate_direct_c2b(phone: str, amount: float, reference: str,
                         account_ref: str = "VoiceUSSD") -> dict:
    """For intents that are genuinely single-leg C2B: Pay Bill, Buy Goods,
    Buy Airtime, Savings Deposit. No B2C follow-up."""

    callback_url = f"{PUBLIC_BASE_URL}/daraja/c2b-result?ref={reference}"
    return stk_push(
        phone=phone, amount=amount,
        callback_url=callback_url, account_ref=account_ref,
    )