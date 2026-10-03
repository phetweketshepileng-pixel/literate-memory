"""Flags job adverts that look like scams, so job seekers are warned before
they apply. South African job scams usually ask for money up front ("admin
fee", "registration fee", "training fee"), dangle unrealistic pay for no
experience, or use a free email address while claiming to be a big employer.

check_job(title, company, description) -> ScamCheck | None
    level "high"    : asks for money, or another strong scam sign
    level "caution" : a sign worth being careful about
Rule-based and explainable: every flag carries the reason shown to the user.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

# a fee word only counts when the applicant is the one paying
_FEE_WORDS = re.compile(
    r"\b(?:registration|admin(?:istration)?|application|processing|training|course|uniform|medical|placement|"
    r"joining|starter[- ]?kit|security|screening|clearance|booking|interview)\s+fees?\b|\bonce[- ]off\s+(?:fee|payment)\b", re.I)
_PAY_CONTEXT = re.compile(r"R\s?\d|\bpay\b|\bpayable\b|\bmust\b|\brequired\b|\bdeposit\b|\bbefore you start\b", re.I)
_NO_FEE = re.compile(r"\bno\b[^.]{0,25}\bfees?\b|free of charge|never (?:ask|charge)|does not charge|won't charge", re.I)
_MONEY_ASK = re.compile(
    r"\bpay(?:ment)?\s+(?:of\s+)?R\s?\d"
    r"|\b(?:pay|deposit|send|transfer)\s+(?:a\s+|the\s+)?(?:once[- ]off\s+)?(?:fee|amount|money|deposit)\b"
    r"|\bfee\s+of\s+R\s?\d"
    r"|\b(?:airtime|e-?wallet|cash\s*send|instant\s+money)\b.{0,40}\b(?:send|pay|deposit)",
    re.I)


def _asks_for_money(text: str) -> bool:
    if _MONEY_ASK.search(text):
        return True
    for m in _FEE_WORDS.finditer(text):
        window = text[max(0, m.start() - 60): m.end() + 60]
        if _NO_FEE.search(window):
            continue
        if _PAY_CONTEXT.search(window):
            return True
    return False


_UNREAL_PAY = re.compile(
    r"\bR\s?(?:[2-9]\d|\d{3})\s?(?:000|k)\b\s*(?:per|a|/)\s*(?:week|day)"
    r"|\bearn\s+(?:up\s+to\s+)?R\s?\d[\d\s,]{3,}\s*(?:per|a|/)\s*(?:week|day)", re.I)
_NO_EXP = re.compile(r"no (?:experience|qualifications?) (?:required|needed)", re.I)
_BIG_PAY = re.compile(r"\bR\s?(?:[3-9]\d|\d{3})\s?(?:000|k)\b", re.I)
_SCHEME = re.compile(r"\b(?:forex|crypto(?:currency)? trading|binary options|pyramid|mlm|multi[- ]level marketing|"
                     r"be your own boss|financial freedom|passive income|recruit (?:friends|others))\b", re.I)
_FREE_MAIL = re.compile(r"[\w.+-]+@(?:gmail|yahoo|ymail|outlook|hotmail|live|webmail\.co\.za|mweb\.co\.za|"
                        r"telkomsa\.net|icloud)\.[\w.]+", re.I)
_WHATSAPP_ONLY = re.compile(r"\b(?:whats\s?app|WA)\b[^.\n]{0,40}\b(?:only|cv|apply|send)", re.I)
_URGENT = re.compile(r"\b(?:limited (?:spaces|spots|slots)|pay (?:today|now)|act (?:fast|now)|"
                     r"first come,? first served|guaranteed (?:job|employment|placement))\b", re.I)
# employers whose real adverts never use a free email address
_BIG_BRANDS = re.compile(r"\b(?:absa|standard bank|fnb|first national|nedbank|capitec|investec|discovery|old mutual|"
                         r"sanlam|momentum|vodacom|mtn|telkom|cell ?c|eskom|transnet|sasol|shoprite|checkers|pick ?n ?pay|"
                         r"woolworths|spar|game|makro|clicks|dis-?chem|sars|saps|department of|municipality|"
                         r"anglo american|de beers|mr ?price|pep|ackermans|takealot|coca-?cola|sab)\b", re.I)


@dataclass
class ScamCheck:
    level: str                      # "high" | "caution"
    reasons: list[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {"level": self.level, "reasons": self.reasons}


def check_job(title: str | None, company: str | None, description: str | None) -> ScamCheck | None:
    text = f"{title or ''}\n{description or ''}"
    high: list[str] = []
    caution: list[str] = []

    if _asks_for_money(text):
        high.append("Asks you to pay money (a fee or deposit). Real employers never charge you to apply or start a job.")
    if _UNREAL_PAY.search(text) or (_NO_EXP.search(text) and _BIG_PAY.search(text)):
        high.append("Promises very high pay for little or no experience.")
    if _SCHEME.search(text):
        high.append("Mentions trading, \"passive income\" or recruiting others, which are signs of a scheme rather than a job.")

    free = _FREE_MAIL.search(text)
    if free and _BIG_BRANDS.search(f"{company or ''} {text}"):
        high.append(f"Claims to be a well-known employer but asks you to reply to a free email address ({free.group(0)}).")
    elif free:
        caution.append(f"Applications go to a free email address ({free.group(0)}). Check the company is real before sending your details.")
    if _WHATSAPP_ONLY.search(text):
        caution.append("Asks you to apply via WhatsApp. Be careful, and never send your ID or bank details this way.")
    if _URGENT.search(text):
        caution.append("Pressures you to act fast or \"guarantees\" a job.")

    if high:
        return ScamCheck("high", high + caution)
    if caution:
        return ScamCheck("caution", caution)
    return None
