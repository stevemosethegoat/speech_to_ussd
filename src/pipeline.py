"""End-to-end pipeline: audio -> ASR -> normalize -> intent -> slots -> USSD.

Every run is saved to data/traces/<run_id>/ so voice input is traceable:
audio.wav, whisper_transcript.txt, and trace.json (intent, slots, USSD).
"""

import os
from pathlib import Path

from src.audio.recorder import save_audio, record_audio
from src.asr.whisper import transcribe
from src.intent.predict import predict_intent, load_model
from src.preprocessing.text_cleaner import clean_swahili_text
from src.slots.extractor import extract_slots
from src.ussd.generator import generate_response
from src.trace import save_trace, new_run_id
from src.pending import save_pending, load_pending, clear_pending
from src.contacts import lookup_contact

CACHE_AUDIO_DIR = Path("data/raw/recordings")


def load_vectorizer(path="models/vectorizer.pkl"):
    """Load the fitted TF-IDF vectorizer."""
    import joblib
    return joblib.load(path)


def run_pipeline(
    audio_path=None,
    slang_dict_path="data/slang_dictionary/swahili_slang_typos.csv",
    model_name="logistic_regression",
    source="file",
    raw_text_override=None,
    record_duration=5,
):
    """Run the full speech-to-USSD pipeline.

    - If audio_path is None, records from the microphone.
    - If raw_text_override is provided, skips ASR (useful for testing).
    """
    steps = []
    audio_path_saved = ""

    # 0. Capture audio (record or use provided file)
    if raw_text_override is None:
        if audio_path is None:
            audio_path_saved = str(
                CACHE_AUDIO_DIR / "recording_temp.wav"
            )
            audio_data = record_audio(duration=record_duration)
            save_audio(audio_data, audio_path_saved)
            source = "mic"
        else:
            audio_path_saved = str(audio_path)
        steps.append({"step": "audio", "value": audio_path_saved})

    # 1. Transcribe with Whisper
    if raw_text_override is not None:
        raw_transcript = raw_text_override
    else:
        raw_transcript = transcribe(audio_path_saved)
    steps.append({"step": "asr", "value": raw_transcript})

    # 2. Normalize text (uses Vivian's text_cleaner, no modifications)
    cleaned = clean_swahili_text(raw_transcript)
    steps.append({"step": "normalized_text", "value": cleaned})

    # 3. Predict intent
    model = load_model(model_name)
    vectorizer = load_vectorizer()
    intent, confidence = predict_intent(cleaned, model, vectorizer)
    steps.append({"step": "intent", "value": intent, "confidence": confidence})

    # 4. Extract slots
    slots = extract_slots(cleaned, intent)

    # Contacts: resolve name -> phone for DISPLAY ONLY.
    # The STK Push uses DARAJA_FIXED_PHONE from .env, not this.
    if not slots.get("phone"):
        lookup_name = slots.get("name") or slots.get("recipient") or ""
        resolved = lookup_contact(lookup_name) if lookup_name else None
        if resolved:
            slots["display_phone"] = resolved
            steps.append({"step": "contact_lookup",
                          "value": f"{lookup_name} -> {resolved}"})
    steps.append({"step": "slots", "value": slots})

    # 5. Generate USSD response
    response = generate_response(intent, slots)
    steps.append({"step": "ussd", "value": response["ussd_menu"]})

    run_id = new_run_id()
    save_trace(
        run_id,
        audio_path=audio_path_saved,
        raw_transcript=raw_transcript,
        normalized_text=cleaned,
        intent=intent,
        confidence=confidence,
        slots=slots,
        ussd_menu=response.get("ussd_menu", ""),
        ussd_sequence=response.get("ussd_sequence", ""),
        steps=steps,
        source=source,
    )

    # 6. Persist as pending action (Pattern B: two-turn confirmation)
    from src.pending import save_pending
    save_pending(
        run_id=run_id,
        intent=intent,
        slots=slots,
        menu=response.get("ussd_menu", ""),
        ussd_sequence=response.get("ussd_sequence", ""),
    )

    result = {
        "run_id": run_id,
        "whisper_transcript": raw_transcript,
        "normalized_text": cleaned,
        "intent": intent,
        "confidence": confidence,
        "slots": slots,
        "ussd_menu": response.get("ussd_menu", ""),
        "ussd_sequence": response.get("ussd_sequence", ""),
        "steps": steps,
    }
    return result


# ============================================================
# PATTERN B — Confirmation flow
# ============================================================

# Intents that trigger an STK Push after the user confirms
PAYMENT_INTENTS = {"SEND_MONEY", "PAY_BILL", "BUY_GOODS",
                   "BUY_AIRTIME", "WITHDRAW", "DEPOSIT"}


def confirm_and_execute(run_id: str, answer: str) -> dict:
    """Second-turn handler: user confirms or cancels a pending action.

    Args:
        run_id:  The run_id from turn 1.
        answer:  "yes" / "y" / "no" / "n" (case-insensitive).

    Returns:
        dict with status and either the Daraja response or an error.
    """
    pending = load_pending(run_id)
    if pending is None:
        return {
            "status": "no_pending_action",
            "run_id": run_id,
            "message": ("No pending action for this run_id "
                        "(expired after 10 minutes or never existed)."),
        }

    answer_norm = (answer or "").strip().lower()

    # Cancellation
    if answer_norm.startswith("n"):
        clear_pending(run_id)
        return {
            "status": "cancelled",
            "run_id": run_id,
            "intent": pending["intent"],
        }

    if not answer_norm.startswith("y"):
        return {
            "status": "unrecognized_answer",
            "run_id": run_id,
            "answer": answer,
        }

    intent = pending["intent"]
    slots = pending["slots"]

    if intent not in PAYMENT_INTENTS:
        clear_pending(run_id)
        return {
            "status": "unhandled_intent",
            "run_id": run_id,
            "intent": intent,
        }

    # Amount for STK Push
    amount = slots.get("amount") or ""

    # STK target: single fixed number from .env (NOT from contacts,
    # NOT from slots). Contacts are display-only.
    phone = os.getenv("DARAJA_FIXED_PHONE", "").strip()
    phone = "".join(ch for ch in phone if ch.isdigit())
    if phone.startswith("0"):
        phone = "254" + phone[1:]
    elif phone.startswith("7") and len(phone) == 9:
        phone = "254" + phone

    if not phone:
        clear_pending(run_id)
        return {
            "status": "missing_fixed_phone",
            "run_id": run_id,
            "message": "DARAJA_FIXED_PHONE not set in .env",
        }

    if not phone or len(phone) < 10:
        clear_pending(run_id)
        return {
            "status": "missing_phone",
            "run_id": run_id,
            "slots": slots,
            "message": ("No phone number in slots. User must say "
                        "'on 0712...' or a contact lookup is needed."),
        }

    if not amount:
        clear_pending(run_id)
        return {
            "status": "missing_amount",
            "run_id": run_id,
            "slots": slots,
        }

    try:
        amount_val = float(amount)
    except (TypeError, ValueError):
        clear_pending(run_id)
        return {
            "status": "invalid_amount",
            "run_id": run_id,
            "amount": amount,
        }

    # Fire the STK Push
    from src.daraja import stk_push

    try:
        daraja_result = stk_push(
            phone=phone,
            amount=amount_val,
            callback_url="https://example.com/callback",   # replace with ngrok later
            account_ref=run_id[:12],
            description=f"VoiceUSSD {intent}"[:13],
        )
    except Exception as e:
        clear_pending(run_id)
        return {
            "status": "daraja_error",
            "run_id": run_id,
            "error": str(e),
        }

    clear_pending(run_id)

    return {
        "status": "stk_sent",
        "run_id": run_id,
        "intent": intent,
        "phone": phone,
        "amount": amount_val,
        "daraja": daraja_result,
    }

