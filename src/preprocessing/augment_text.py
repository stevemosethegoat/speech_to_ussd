"""Synthetic Sheng/Swahili intent data generator.

Produces data/metadata/synthetic_intent_dataset.csv with the schema:
    id, transcript, intent, amount, recipient, service, ussd_sequence, is_synthetic

Downstream pipeline:
    prepare_dataset.py  ->  splits into train/val/test
    train_intent.py     ->  trains classifier
    pipeline.py         ->  inference (main.py --text / --record)
"""
import csv
import random
import re
import sys
from pathlib import Path

rng = random.Random(7)

# ---------- Amount normalization map (kept for backward compat) ----------
AMOUNT_NORM_MAP = {
    "soo tano": "500", "elfu moja": "1000", "fifty bob": "50", "bob mbao": "20",
    "soo mbili": "200", "elfu mbili": "2000", "punch": "500", "mbao": "20",
    "chapaa soo tano": "500", "Ksh 500": "500",
}

# ---------- USSD mappings ----------
USSD_MAPPINGS = {
    "SEND_MONEY":     "*334# -> 1 -> {recipient} -> {amount}",
    "BUY_AIRTIME":    "*334# -> 3 -> 1 -> {recipient} -> {amount}",
    "CHECK_BALANCE":  "*334# -> 6 -> 1",
    "BUY_BUNDLES":    "*334# -> 3 -> 2 -> {amount}",
    "PAY_BILL":       "*334# -> 2 -> 1 -> {service} -> {recipient} -> {amount}",
    "WITHDRAW_CASH":  "*334# -> 4 -> 1 -> {amount}",
    "DEPOSIT_MONEY":  "*334# -> 4 -> 2 -> {amount}",
    "BUY_TOKENS":     "*334# -> 2 -> 1 -> 888880 -> {recipient} -> {amount}",
    "LOAN":           "*334# -> 5 -> 1 -> {amount}",
}

# ---------- Vocabulary ----------
U = ["", "moja", "mbili", "tatu", "nne", "tano", "sita", "saba", "nane", "tisa"]
EN = {10: "ten", 20: "twenty", 30: "thirty", 50: "fifty", 100: "one hundred", 200: "two hundred",
      250: "two fifty", 300: "three hundred", 500: "five hundred", 1000: "one thousand",
      1500: "fifteen hundred", 2000: "two thousand", 5000: "five thousand"}


def slang(n):
    o = []
    if n == 20: o = ["mbao"]
    elif n == 100: o = ["mia"]
    elif n == 500: o = ["nusu buku", "nusu ngovo", "mia tano"]
    elif n == 1000: o = ["buku", "ngovo", "ngiri", "1k", "kei moja"]
    elif n == 1500: o = ["buku na nusu", "1.5k"]
    elif n % 100 == 0 and 200 <= n <= 900: o = [f"mia {U[n//100]}"]
    elif n % 1000 == 0 and 2000 <= n <= 9000:
        k = n // 1000; o = [f"{k} kei", f"{k}k", f"{k} buku", f"buku {U[k]}", f"ngovo {U[k]}"]
    elif n % 1000 == 0 and 10000 <= n <= 20000:
        k = n // 1000; o = [f"{k} kei", f"{k}k", f"{k} buku"]
    return rng.choice(o) if o else None


def amt(n):
    s = slang(n)
    forms = [("d", 22), ("bob", 14), ("slang", 42 if s else 0), ("ksh", 3),
             ("en", 8 if n in EN else 0), ("enbob", 6 if n in EN else 0)]
    f = rng.choices([a for a, _ in forms], [w for _, w in forms])[0]
    return {"d": str(n), "bob": f"{n} bob", "slang": s, "ksh": f"ksh {n}",
            "en": EN.get(n, ""), "enbob": f"{EN.get(n, '')} bob"}[f]


KIN = ["mathee", "mathe", "buda", "mzae", "shosh", "shosho", "cucu", "brathe", "dem wangu", "sistaa",
       "msee wangu", "chali yangu", "mshikaji wangu", "msupa wangu", "wifey", "mdosi", "mtoi wangu",
       "bestie", "fam", "mama mboga", "fundi"]
NICK = ["Kevo", "Brayo", "Omosh", "Mwas", "Wafula", "Muthoni", "Nyambura", "Kimani", "Otis", "Vinny",
        "Jose", "Shix", "Sharon", "Kush", "Wawira", "Ouma", "Kip", "Wanjiru", "Ian", "Cate"]
PFX = ["0700", "0710", "0712", "0720", "0722", "0723", "0725", "0728",
       "0790", "0794", "0795", "0110", "0112", "0114"]


def phone(): return rng.choice(PFX) + "".join(rng.choice("0123456789") for _ in range(6))


def rec():
    k = rng.choices(["p", "k", "n"], [.30, .45, .25])[0]
    if k == "p": return phone()
    if k == "k": return rng.choice(KIN)
    return rng.choice(NICK)


def kr(r): return (rng.choice(["kwa ", "kwa ", ""]) + r)


OBJ = ["ganji", "doh", "mkwanja", "chapaa", "hiyo ganji", "pesa", "cash", "mpesa"]
PRE = ["manze", "aki", "bana", "wueh", "oya", "sasa", "niaje", "sheesh", "bro", "msee", "buda", "fam", "eeh"]
POST = ["tu", "tu", "fasta", "chap chap", "plis", "kwanza", "sawa", "fiti", "poa", "bro", "haraka"]
SELF = ["kwa simu yangu", "kwa number yangu", "yangu", "kwangu"]
PER = ["ya siku", "ya wiki", "za usiku", "ya mwezi"]

SEND_V = ["tuma"] * 3 + ["nitumie", "nirushie", "nirushie", "mtumie", "mrushie", "msort", "nisort",
                          "msaidie na", "wekea", "weka", "send", "send"]
AIR_V = ["nijazie tokens", "nijazie credit", "nishikie tokens", "nishikie airtime", "niwekee credit",
         "niwekee tokens", "nipee airtime", "nipe tokens", "weka tokens", "weka credit", "tuma tokens",
         "mrushie tokens", "mjazie tokens", "nunua tokens", "top up", "topup", "niwekee jahazi",
         "nishikie jahazi", "tuma airtime", "nipe airtime"]
BUN_V = ["nipe bando", "weka bando", "nunua bando", "nipee bandos", "weka MBs", "nipe MBs",
         "nijazie data", "nishikie bundles", "niwekee bundles", "niwekee bando", "nunua data",
         "nipe data", "nijazie bando", "buy data"]
BILL_V = ["sort", "nisortie", "nisort", "lipia", "nilipie", "lipa", "lipa", "pay", "lipa bili", "weka"]

BILLERS = [("KPLC", "888880", 11, ["stima", "kplc", "tokens za stima", "stima ya nyumba"]),
           ("KPLC postpaid", "888888", 10, ["bili ya stima", "kplc bili"]),
           ("DStv", "444900", 10, ["dstv", "dstv ya nyumba"]),
           ("GOtv", "423655", 10, ["gotv"]),
           ("Zuku", "320320", 8, ["zuku", "wifi ya zuku"]),
           ("Nairobi Water", "444400", 8, ["maji", "bili ya maji"]),
           ("NHIF", "200222", 8, ["nhif"])]
ACP = ["account ", "akaunti ", "meter ", "meter number ", "namba ", "account number "]
PBX = ["paybill ", "paybill number ", "business number "]

BAL = ["cheki balance ya {O}", "nicheki salio ya {O}", "cheki {O} yangu", "nimebaki na ngapi kwa {O}",
       "niko na ngapi kwa {O}", "{O} imebaki ngapi", "salio ya {O} ni aje", "niangalie {O} balance",
       "balance ya {O} ni ngapi", "nione {O} balance", "nina {O} ngapi", "nimeachwa na ngapi kwa {O}"]
BAL0 = ["nimebaki na ngapi", "nina ganji ngapi", "cheki balance", "niko na ngapi",
        "nicheki salio", "ganji imebaki ngapi"]
BO = {"M-Pesa": ["mpesa", "pesa", "doh", "ganji"],
      "airtime": ["tokens", "credit", "airtime", "jahazi"],
      "data": ["bando", "MBs", "data"],
      "Bonga": ["bonga", "bonga points"]}

AGENT_V = ["toa", "toa pesa", "withdraw", "nitoe", "nitolee", "toa doh", "toa ganji", "withdraw cash"]
DEPOSIT_V = ["weka", "weka pesa", "deposit", "niweke", "niwekee", "weka doh", "weka ganji", "save"]
AGENT_W = ["kwa agent", "kwa wakili", "kwa shop", "kwa duka", "kwa mtu", "agent", "hapa"]
TOKEN_V = ["nunua tokens", "nunua stima", "buy tokens", "nijazie stima", "weka stima", "nunua umeme",
           "nipe tokens", "tuma tokens", "lipa stima", "nunua tokens za stima"]
TOKEN_W = ["tokens za stima", "stima", "umeme", "tokens", "kplc tokens", "prepaid"]
LOAN_V = ["kopa", "nikope", "niokoe", "nidai", "nidaiwe", "kopa doh", "kopa ganji",
          "fuliza", "nifullize", "nifultilize", "borrow"]
LOAN_W = ["fuliza", "fuliza ya", "kwa fuliza", "loan", "mkopo"]


def wrap(t):
    if rng.random() < .35: t = rng.choice(PRE) + " " + t
    if rng.random() < .35: t += " " + rng.choice(POST)
    return re.sub(r"\s+", " ", t).strip()


def amount_for(it):
    L = {"SEND_MONEY": [50, 100, 200, 300, 500, 1000, 1500, 2000, 3000, 5000, 10000],
         "BUY_AIRTIME": [10, 20, 30, 50, 100, 200, 250, 500, 1000],
         "BUY_BUNDLES": [10, 20, 50, 99, 100, 250, 500, 1000, 2000],
         "PAY_BILL": [100, 200, 500, 1000, 1500, 2000, 3000, 5000],
         "WITHDRAW_CASH": [100, 200, 500, 1000, 1500, 2000, 3000, 5000, 10000],
         "DEPOSIT_MONEY": [100, 200, 500, 1000, 1500, 2000, 3000, 5000],
         "BUY_TOKENS": [50, 100, 200, 500, 1000, 2000, 3000, 5000],
         "LOAN": [100, 200, 500, 1000, 1500, 2000, 2500, 3000, 5000]}[it]
    return rng.choice(L)


def send():
    n, r = amount_for("SEND_MONEY"), rec(); a = amt(n); v = rng.choice(SEND_V); o = rng.choice(OBJ)
    t = rng.choice([f"{v} {r} {a}", f"{v} {a} {kr(r)}", f"{v} {o} ya {a} {kr(r)}",
                    f"{v} {kr(r)} {o} ya {a}", f"{v} {r} {o} ya {a}", f"{v} {a} {r}",
                    f"{v} {r} kwa {a}", f"{v} {a} {o} {kr(r)}"])
    ussd = USSD_MAPPINGS["SEND_MONEY"].format(
        recipient=(r.lower() if not r[0].isdigit() else r), amount=n)
    return {"id": "", "transcript": wrap(t), "intent": "SEND_MONEY", "amount": n,
            "recipient": r, "service": "", "ussd_sequence": ussd, "is_synthetic": True}


def air():
    n = amount_for("BUY_AIRTIME"); a = amt(n); v = rng.choice(AIR_V)
    r = rec() if rng.random() < .45 else None
    if r:
        t = rng.choice([f"{v} ya {a} {kr(r)}", f"{v} {a} {kr(r)}", f"{v} {r} ya {a}", f"{v} {r} {a}"])
    else:
        t = rng.choice([f"{v} ya {a}", f"{v} {a}", f"{v} ya {a} {rng.choice(SELF)}", f"{v} {a} {rng.choice(SELF)}"])
    rr = r or "self"
    ussd = USSD_MAPPINGS["BUY_AIRTIME"].format(
        recipient=(r.lower() if r and not r[0].isdigit() else rr), amount=n)
    return {"id": "", "transcript": wrap(t), "intent": "BUY_AIRTIME", "amount": n,
            "recipient": r or "", "service": "", "ussd_sequence": ussd, "is_synthetic": True}


def bun():
    n = amount_for("BUY_BUNDLES"); a = amt(n); v = rng.choice(BUN_V); p = rng.choice(PER)
    t = rng.choice([f"{v} ya {a}", f"{v} {a}", f"{v} kwa {a}", f"{v} ya {a} {rng.choice(SELF)}",
                    f"{v} {a} {p}", f"{v} {p} ya {a}"])
    ussd = USSD_MAPPINGS["BUY_BUNDLES"].format(amount=n)
    return {"id": "", "transcript": wrap(t), "intent": "BUY_BUNDLES", "amount": n,
            "recipient": "", "service": "", "ussd_sequence": ussd, "is_synthetic": True}


def bill():
    name, pb, L, al = rng.choice(BILLERS); alias = rng.choice(al)
    n = amount_for("PAY_BILL"); a = amt(n)
    acct = "".join(rng.choice("0123456789") for _ in range(L))
    ac = rng.choice(ACP) + acct; v = rng.choice(BILL_V)
    if v == "weka":
        alias = "tokens za stima" if name == "KPLC" else alias
        v = "weka" if name == "KPLC" else "lipa"
    t = rng.choice([f"{v} {alias} {a} {ac}", f"{v} {alias} {ac} {a}", f"{v} {alias} ya {a} {ac}",
                    f"{v} {a} kwa {alias} {ac}",
                    f"{v} paybill {pb} {ac} {a}".replace("paybill ", rng.choice(PBX), 1)])
    ussd = USSD_MAPPINGS["PAY_BILL"].format(service=pb, recipient=acct, amount=n)
    return {"id": "", "transcript": wrap(t), "intent": "PAY_BILL", "amount": n,
            "recipient": acct, "service": name, "ussd_sequence": ussd, "is_synthetic": True}


def bal():
    svc = rng.choices(list(BO), [45, 25, 20, 10])[0]
    if rng.random() < .22:
        t, svc = rng.choice(BAL0), "M-Pesa"
    else:
        t = rng.choice(BAL).format(O=rng.choice(BO[svc]))
    return {"id": "", "transcript": wrap(t), "intent": "CHECK_BALANCE", "amount": "",
            "recipient": "", "service": svc, "ussd_sequence": USSD_MAPPINGS["CHECK_BALANCE"],
            "is_synthetic": True}


def withdraw():
    n = amount_for("WITHDRAW_CASH"); a = amt(n); v = rng.choice(AGENT_V); w = rng.choice(AGENT_W)
    if rng.random() < .2: v = "nitolee"
    t = rng.choice([f"{v} {a} {w}", f"{v} {a}", f"{w} {v} {a}", f"{v} pesa {a} {w}", f"{v} doh {a}"])
    ussd = USSD_MAPPINGS["WITHDRAW_CASH"].format(amount=n)
    return {"id": "", "transcript": wrap(t), "intent": "WITHDRAW_CASH", "amount": n,
            "recipient": "", "service": "", "ussd_sequence": ussd, "is_synthetic": True}


def deposit():
    n = amount_for("DEPOSIT_MONEY"); a = amt(n); v = rng.choice(DEPOSIT_V); w = rng.choice(AGENT_W)
    t = rng.choice([f"{v} {a} {w}", f"{v} {a}", f"{w} {v} {a}", f"{v} pesa {a} {w}", f"{v} doh {a}"])
    ussd = USSD_MAPPINGS["DEPOSIT_MONEY"].format(amount=n)
    return {"id": "", "transcript": wrap(t), "intent": "DEPOSIT_MONEY", "amount": n,
            "recipient": "", "service": "", "ussd_sequence": ussd, "is_synthetic": True}


def tokens():
    n = amount_for("BUY_TOKENS"); a = amt(n); v = rng.choice(TOKEN_V); w = rng.choice(TOKEN_W)
    t = rng.choice([f"{v} {a}", f"{v} {w} {a}", f"{v} {a} {w}", f"{w} {a}", f"{v} ya {a}"])
    ussd = USSD_MAPPINGS["BUY_TOKENS"].format(recipient="888880", amount=n)
    return {"id": "", "transcript": wrap(t), "intent": "BUY_TOKENS", "amount": n,
            "recipient": "888880", "service": "KPLC", "ussd_sequence": ussd, "is_synthetic": True}


def loan():
    n = amount_for("LOAN"); a = amt(n); v = rng.choice(LOAN_V); w = rng.choice(LOAN_W)
    t = rng.choice([f"{v} {a}", f"{v} {a} {w}", f"{v} {w} {a}", f"{v} doh {a}", f"{v} pesa {a}"])
    ussd = USSD_MAPPINGS["LOAN"].format(amount=n)
    return {"id": "", "transcript": wrap(t), "intent": "LOAN", "amount": n,
            "recipient": "", "service": "", "ussd_sequence": ussd, "is_synthetic": True}


def save_dataset(data: list, output_path: Path):
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = ["id", "transcript", "intent", "amount", "recipient",
                  "service", "ussd_sequence", "is_synthetic"]
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(data)
    print(f"Successfully generated and saved {len(data)} synthetic rows to {output_path}")


def main(n_total: int = 2000):
    mix = [(send, .18), (air, .15), (bun, .12), (bill, .12), (bal, .13),
           (withdraw, .10), (deposit, .08), (tokens, .07), (loan, .05)]
    rows, seen = [], set()
    for fn, w in mix:
        got, tries = 0, 0
        while got < int(n_total * w) and tries < 200000:
            tries += 1
            r = fn()
            if r["transcript"].lower() in seen:
                continue
            seen.add(r["transcript"].lower())
            rows.append(r)
            got += 1
    rng.shuffle(rows)
    for i, r in enumerate(rows, 1):
        r["id"] = f"syn_{i:04d}"
    return rows


if __name__ == "__main__":
    PROJECT_ROOT = Path(__file__).resolve().parents[2]
    OUT = PROJECT_ROOT / "data" / "metadata" / "synthetic_intent_dataset.csv"
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 2000
    data = main(n)
    save_dataset(data, OUT)
