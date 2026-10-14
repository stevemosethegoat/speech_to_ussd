"""Sheng normalizer — fixes Whisper's phoneme-level mistakes.

Maps common misspellings of Sheng denominations and phrases back to
their canonical form. Run this AFTER transcription, BEFORE the intent
classifier.
"""

import json
import re
from pathlib import Path


def load_vocab(path: str = "data/sheng_amounts.json") -> dict:
    try:
        return json.loads(Path(path).read_text())
    except Exception:
        return {}


# Common Whisper mishearings of Sheng terms -> canonical form.
SHENG_REPLACEMENTS = {
    # Money units
    "mbau":         "mbao",
    "mbaoh":        "mbao",
    "baoh":         "mbao",
    "mbalu":        "mbao",
    "thau":         "thao",
    "tao":          "thao",
    "kapar":        "kapaa",
    "ngwani":       "ngwanye",
    "azari":        "azar",
    "brambah":      "bramba",

    # Money slang
    "chapa":        "chapaa",
    "mundez":       "munde",
    "ganjee":       "ganji",
    "mkwanjah":     "mkwanja",
    "doh":          "doe",

    # M-Pesa product terms
    "mpesa":        "M-Pesa",
    "m pesa":       "M-Pesa",
    "em pesa":      "M-Pesa",
    "m-pesa":       "M-Pesa",
    "fuliser":      "fuliza",
    "mshwari":      "M-Shwari",
    "m shwari":     "M-Shwari",
    "m-shwari":     "M-Shwari",
    "mshuari":      "M-Shwari",
    "kcb mpesa":    "KCB M-Pesa",

    # Transaction verbs
    "duma":         "tuma",
    "dhuma":        "tuma",
    "tumah":        "tuma",
    "dooma":        "tuma",
    "leepa":        "lipa",
    "wekha":        "weka",
    "toah":         "toa",
}


def normalize_sheng(text: str, vocab_path: str = "data/sheng_amounts.json") -> str:
    """Normalize Whisper output for Sheng phrases."""
    if not text:
        return text
    text = re.sub(r"\s+", " ", text).strip()
    for wrong, right in SHENG_REPLACEMENTS.items():
        pattern = re.compile(
            r"(?<![a-zA-Z])" + re.escape(wrong) + r"(?![a-zA-Z])",
            re.IGNORECASE,
        )
        text = pattern.sub(right, text)
    # Fix repeated tokens
    text = re.sub(r"\b(\S+)(\s+\1){2,}\b", r"\1", text)
    return text


def extract_amounts(text: str, vocab_path: str = "data/sheng_amounts.json") -> list[dict]:
    """Extract money amounts from a Sheng transcript."""
    vocab = load_vocab(vocab_path)
    found = []

    # Numeric amount + optional money word
    for m in re.finditer(r"\b(\d{1,7})\s*(bob|shillings?|ksh|sh)?\b", text, re.IGNORECASE):
        n = int(m.group(1))
        if n > 0:
            found.append({"raw": m.group(0).strip(), "value": n, "kind": "numeric"})

    # Numeric amount × unit ("2 mbao", "3 thao")
    for m in re.finditer(r"\b(\d{1,3})\s+(\w+)\b", text, re.IGNORECASE):
        qty, unit = int(m.group(1)), m.group(2).lower()
        if unit in vocab.get("units", {}):
            found.append({
                "raw": m.group(0).strip(),
                "value": qty * vocab["units"][unit],
                "kind": "unit", "unit": unit, "qty": qty,
            })

    # Bare unit words ("mbao", "ngiri")
    for unit, value in vocab.get("units", {}).items():
        for _ in re.finditer(r"(?<![a-zA-Z])" + re.escape(unit) + r"(?![a-zA-Z])", text, re.IGNORECASE):
            found.append({"raw": unit, "value": value, "kind": "unit", "unit": unit, "qty": 1})

    # Fixed phrases
    for phrase, value in vocab.get("fixed", {}).items():
        for _ in re.finditer(re.escape(phrase), text, re.IGNORECASE):
            found.append({"raw": phrase, "value": value, "kind": "fixed"})

    seen = set()
    unique = []
    for f in found:
        if f["raw"] in seen:
            continue
        seen.add(f["raw"])
        unique.append(f)
    return unique


if __name__ == "__main__":
    tests = [
        "tuma mbao kwa john",
        "lipa 500 bob kwa KPLC",
        "tuma ngiri mbili kwa mary",
        "nataka kidole moja ya airtime",
        "duma punch wa mum",
    ]
    for t in tests:
        norm = normalize_sheng(t)
        amts = extract_amounts(norm)
        print(f"in:  {t}")
        print(f"out: {norm}")
        print(f"amt: {amts}")
        print()
