from contacts import confirm_contact
from src.ussd.generator import generate_response

# *334# MENU TREE
USSD_MENU = {
    "root": {"options": {
        "1": {"label": "Send Money", "next": "send_money"},
        "2": {"label": "Withdraw Cash", "next": "withdraw_cash"},
        "3": {"label": "Buy Airtime", "next": "buy_airtime"},
        "4": {"label": "Lipa na M-PESA", "next": "lipa_na_mpesa"},
        "5": {"label": "My Account", "next": "my_account"},
        "6": {"label": "Loans and Savings", "next": "loans_savings"},
        "7": {"label": "Financial Services", "next": "financial_services"},
    }},
    "send_money": {"options": {
        "1": {"label": "To Any Network", "action": "SEND_MONEY_ANY_NETWORK"},
        "2": {"label": "M-PESA Global", "action": "SEND_MONEY_GLOBAL"},
        "3": {"label": "Pochi la Biashara", "next": "pochi"},
    }},
    "withdraw_cash": {"options": {
        "1": {"label": "From Agent", "action": "WITHDRAW_AGENT"},
        "2": {"label": "From ATM", "action": "WITHDRAW_ATM"},
        "3": {"label": "From Bank to M-PESA", "action": "WITHDRAW_BANK"},
    }},
    "buy_airtime": {"options": {
        "1": {"label": "Buy Airtime", "action": "BUY_AIRTIME"},
        "2": {"label": "Data Deals", "action": "BUY_BUNDLES"},
        "3": {"label": "Minutes", "action": "BUY_MINUTES"},
    }},
    "lipa_na_mpesa": {"options": {
        "1": {"label": "Pay Bill", "action": "PAY_BILL"},
        "2": {"label": "Buy Goods and Services", "action": "BUY_GOODS"},
        "3": {"label": "Pochi La Biashara", "next": "pochi"},
        "4": {"label": "T-Kash", "action": "TKASH"},
        "5": {"label": "Bill Manager", "action": "BILL_MANAGER"},
        "6": {"label": "GlobalPay", "action": "GLOBALPAY"},
        "7": {"label": "County Services", "action": "COUNTY_SERVICES"},
        "8": {"label": "Transport and Parking", "action": "TRANSPORT_PARKING"},
    }},
    "pochi": {"options": {
        "1": {"label": "Send Money", "action": "POCHI_SEND_MONEY"},
        "2": {"label": "Lipa na Pochi", "action": "POCHI_LIPA"},
        "3": {"label": "Move Money", "action": "POCHI_MOVE_MONEY"},
        "4": {"label": "Withdraw from Agent", "action": "POCHI_WITHDRAW"},
        "5": {"label": "ZIIDI for Pochi", "action": "POCHI_ZIIDI"},
        "6": {"label": "Taasi Pochi Loans", "action": "POCHI_LOANS"},
        "7": {"label": "Ofa ya Pochi", "action": "POCHI_OFFER"},
        "8": {"label": "Sell Airtime", "action": "POCHI_SELL_AIRTIME"},
        "9": {"label": "My Account", "action": "POCHI_MY_ACCOUNT"},
    }},
    "my_account": {"options": {
        "1": {"label": "Unlock M-PESA PIN", "action": "UNLOCK_PIN"},
        "2": {"label": "M-PESA PIN Manager", "action": "PIN_MANAGER"},
        "3": {"label": "M-PESA Statement", "action": "STATEMENT"},
        "4": {"label": "Check Balance", "action": "CHECK_BALANCE"},
        "5": {"label": "Tariff Query", "action": "TARIFF_QUERY"},
    }},
    "loans_savings": {"options": {
        "1": {"label": "Fuliza M-PESA", "next": "fuliza"},
        "2": {"label": "M-Shwari", "action": "MSHWARI"},
        "3": {"label": "KCB M-PESA", "action": "KCB_MPESA"},
        "4": {"label": "Timiza", "action": "TIMIZA"},
        "5": {"label": "Kilimo Float", "action": "KILIMO_FLOAT"},
        "6": {"label": "Cash Advance", "action": "CASH_ADVANCE"},
        "7": {"label": "Halal Pesa", "action": "HALAL_PESA"},
    }},
    "fuliza": {"options": {
        "1": {"label": "Check My Limit", "action": "FULIZA_CHECK_LIMIT"},
        "2": {"label": "My Fuliza Balance", "action": "FULIZA_BALANCE"},
        "3": {"label": "Query Charges", "action": "FULIZA_CHARGES"},
        "4": {"label": "Lipa Fuliza with Bonga", "action": "FULIZA_BONGA"},
        "5": {"label": "Pay Fuliza on Recycled Line", "action": "FULIZA_RECYCLED"},
        "6": {"label": "Refresh My Limit", "action": "FULIZA_REFRESH"},
        "7": {"label": "Mini Statement", "action": "FULIZA_STATEMENT"},
        "8": {"label": "Know more about FULIZA", "action": "FULIZA_INFO"},
        "9": {"label": "Opt out", "action": "FULIZA_OPT_OUT"},
    }},
    "financial_services": {"options": {
        "1": {"label": "ZIIDI", "action": "ZIIDI"},
        "2": {"label": "Tuunza", "action": "TUUNZA"},
        "3": {"label": "M-Banking", "action": "MBANKING"},
        "4": {"label": "SACCOs", "action": "SACCOS"},
        "5": {"label": "myGroup", "action": "MYGROUP"},
        "6": {"label": "Insurance", "action": "INSURANCE"},
        "7": {"label": "Wealth Management", "action": "WEALTH_MGMT"},
        "8": {"label": "Unclaimed Funds", "action": "UNCLAIMED_FUNDS"},
        "9": {"label": "MALI", "action": "MALI"},
    }},
}

#  RESPONSES FOR NON-CORE ACTIONS 
ACTION_RESPONSES = {
    "WITHDRAW_AGENT": "Withdraw Cash from Agent\nEnter agent number:",
    "WITHDRAW_ATM": "Withdraw Cash from ATM\nEnter amount:",
    "WITHDRAW_BANK": "From Bank to M-PESA\nEnter amount:",
    "BUY_MINUTES": "Minutes\nEnter amount:",
    "SEND_MONEY_GLOBAL": "M-PESA Global\nEnter recipient country:",
    "POCHI_SEND_MONEY": "Pochi la Biashara - Send Money\nEnter recipient:",
    "POCHI_LIPA": "Lipa na Pochi\nEnter till number:",
    "POCHI_MOVE_MONEY": "Move Money\nEnter amount:",
    "POCHI_WITHDRAW": "Withdraw from Agent\nEnter agent number:",
    "POCHI_ZIIDI": "ZIIDI for Pochi\nEnter amount:",
    "POCHI_LOANS": "Taasi Pochi Loans\nEnter amount:",
    "POCHI_OFFER": "Ofa ya Pochi\nView current offers.",
    "POCHI_SELL_AIRTIME": "Sell Airtime\nEnter amount:",
    "POCHI_MY_ACCOUNT": "Pochi My Account\nView account details.",
    "BUY_GOODS": "Buy Goods and Services\nEnter till number:",
    "TKASH": "T-Kash\nEnter phone number:",
    "BILL_MANAGER": "Bill Manager\nView upcoming bills.",
    "GLOBALPAY": "GlobalPay\nEnter merchant details:",
    "COUNTY_SERVICES": "County Services\nSelect your county:",
    "TRANSPORT_PARKING": "Transport and Parking\nEnter parking zone:",
    "UNLOCK_PIN": "Unlock M-PESA PIN\nFollow prompts to reset your PIN.",
    "PIN_MANAGER": "M-PESA PIN Manager\nManage your PIN settings.",
    "STATEMENT": "M-PESA Statement\nSelect statement period:",
    "TARIFF_QUERY": "Tariff Query\nView M-PESA transaction charges.",
    "MSHWARI": "M-Shwari\nAccess savings and loans.",
    "KCB_MPESA": "KCB M-PESA\nAccess KCB M-PESA services.",
    "TIMIZA": "Timiza\nAccess Timiza loan services.",
    "KILIMO_FLOAT": "Kilimo Float\nAccess agricultural credit.",
    "CASH_ADVANCE": "Cash Advance\nCheck available advance.",
    "HALAL_PESA": "Halal Pesa\nAccess Sharia-compliant savings.",
    "FULIZA_CHECK_LIMIT": "Your Fuliza limit is KSh [LIMIT].",
    "FULIZA_BALANCE": "Your current Fuliza balance is KSh [BALANCE].",
    "FULIZA_CHARGES": "Fuliza charges depend on amount and duration borrowed.",
    "FULIZA_BONGA": "Lipa Fuliza with Bonga Points\nConfirm redemption:",
    "FULIZA_RECYCLED": "Pay Fuliza on Recycled Line\nConfirm payment:",
    "FULIZA_REFRESH": "Your Fuliza limit has been refreshed.",
    "FULIZA_STATEMENT": "Fuliza Mini Statement\nView recent transactions.",
    "FULIZA_INFO": "Fuliza is an M-PESA overdraft service.",
    "FULIZA_OPT_OUT": "You have opted out of Fuliza M-PESA.",
    "ZIIDI": "ZIIDI\nAccess ZIIDI money market fund.",
    "TUUNZA": "Tuunza\nAccess Tuunza savings plan.",
    "MBANKING": "M-Banking\nLink your bank account.",
    "SACCOS": "SACCOs\nAccess SACCO services.",
    "MYGROUP": "myGroup\nManage your group/chama.",
    "INSURANCE": "Insurance\nAccess insurance products.",
    "WEALTH_MGMT": "Wealth Management\nAccess investment products.",
    "UNCLAIMED_FUNDS": "Unclaimed Funds\nCheck for unclaimed funds.",
    "MALI": "MALI\nAccess MALI investment services.",
}

CORE_INTENT_MAP = {
    "SEND_MONEY_ANY_NETWORK": "send_money",
    "PAY_BILL": "pay_bill",
    "CHECK_BALANCE": "check_balance",
    "BUY_AIRTIME": "buy_airtime",
    "BUY_BUNDLES": "buy_bundles",
}


# MENU NAVIGATION 
def get_menu(menu_key="root"):
    menu = USSD_MENU.get(menu_key)
    return {k: v["label"] for k, v in menu["options"].items()} if menu else None


def select_option(menu_key, choice):
    menu = USSD_MENU.get(menu_key)
    if not menu:
        return {"type": "invalid"}
    option = menu["options"].get(choice)
    if not option:
        return {"type": "invalid"}
    if "next" in option:
        return {"type": "menu", "menu_key": option["next"]}
    return {"type": "action", "action": option["action"]}


def resolve_action(action, slots=None):
    slots = slots or {}
    if action in CORE_INTENT_MAP:
        return generate_response(CORE_INTENT_MAP[action], slots)
    message = ACTION_RESPONSES.get(action)
    if message:
        return {"status": "ready", "ussd_menu": message}
    return {"status": "not_found", "message": f"No response for '{action}'"}

#PROCESS_REQUEST 
def process_request(intent, amount=None, recipient_name=None, user_reply=None, service=None):
    intent = intent.lower()
    slots = {"amount": amount, "service": service}

    if intent in ("send_money", "sendmoney"):
        contact_result = confirm_contact(recipient_name, user_reply)
        if contact_result["status"] != "confirmed":
            return contact_result
        slots["recipient"] = contact_result["number"]
        return generate_response(intent, slots)

    slots["recipient"] = recipient_name
    return generate_response(intent, slots)


if __name__ == "__main__":
    # Test the tree navigation: root -> Loans -> Fuliza -> Pay with Bonga
    r1 = select_option("root", "6")
    r2 = select_option(r1["menu_key"], "1")
    r3 = select_option(r2["menu_key"], "4")
    print(resolve_action(r3["action"]))

    # Test existing core flow works
    print(process_request("SEND_MONEY", amount=500, recipient_name="John", user_reply="yes"))
