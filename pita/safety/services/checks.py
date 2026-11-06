"""Deterministic signals for 'Is this safe?' (plan.md §7.4): redaction, URL parsing (never fetching) and scam rules."""
import re
import unicodedata
from urllib.parse import urlsplit

# ── Redaction (before storage and before anything leaves Django) ──
_EMAIL = re.compile(r'\b[\w.+-]+@[\w-]+(?:\.[\w-]+)+\b')
_PHONE = re.compile(r'(?<![\w+])(?:\+?256[\s-]?|0)7\d{2}[\s-]?\d{3}[\s-]?\d{3}(?!\w)')
_SECRET = re.compile(r'(?i)\b(pin|otp|code|password|passcode)(\s*(?:is|:|=|-)\s*)([^\s,.;]{3,})')
_CODE = re.compile(r'(?<![\d,.])(?!(?:19|20)\d\d(?![\d,.]))\d{4,8}(?![\d,.])')   # keeps years like 2027


def redact(text: str) -> str:
    text = _EMAIL.sub('[EMAIL]', text)
    text = _PHONE.sub('[PHONE]', text)
    text = _SECRET.sub(lambda m: f'{m.group(1)}{m.group(2)}[SECRET]', text)
    return _CODE.sub('[CODE]', text)


# ── URLs: parsed as inert text ──
_URL = re.compile(r'(?i)\b((?:https?://|www\.)[^\s<>"\']+|[a-z0-9-]+(?:\.[a-z0-9-]+)*\.(?:com|ug|net|org|xyz|top|info|click|link|site|online|example|ly|co|io|me)(?:/[^\s<>"\']*)?)')
_SHORTENERS = {'bit.ly', 'tinyurl.com', 'cutt.ly', 'is.gd', 't.co', 'ow.ly', 'rb.gy', 'shorturl.at', 'tiny.cc'}
_ODD_TLDS = {'xyz', 'top', 'click', 'link', 'site', 'online', 'info', 'zip', 'mov'}
# Brands commonly impersonated in Ugandan scams → official domains (verify before relying on them)
OFFICIAL_DOMAINS = {
    'MTN Uganda': ['mtn.co.ug'], 'Airtel Uganda': ['airtel.co.ug'], 'Makerere University': ['mak.ac.ug'],
    'Centenary Bank': ['centenarybank.co.ug'], 'UNICEF Uganda': ['unicef.org'], 'Stanbic Bank': ['stanbicbank.co.ug'],
}
_BRAND_WORDS = {'MTN Uganda': r'\bmtn\b|\bmomo\b', 'Airtel Uganda': r'\bairtel\b', 'Makerere University': r'\bmakerere\b',
                'Centenary Bank': r'\bcentenary\b', 'UNICEF Uganda': r'\bunicef\b', 'Stanbic Bank': r'\bstanbic\b'}


def extract_urls(text: str) -> list[str]:
    seen = []
    for m in _URL.finditer(text):
        u = m.group(1).rstrip('.,);!?')
        if u not in seen:
            seen.append(u)
    return seen[:20]


def host_of(url: str) -> str:
    u = url if '://' in url else 'http://' + url
    return (urlsplit(u).hostname or '').lower().rstrip('.')


def claimed_organisation(text: str) -> str | None:
    t = text.lower()
    for org, pattern in _BRAND_WORDS.items():
        if re.search(pattern, t):
            return org
    return None


def url_signals(url: str, org: str | None) -> list[str]:
    host = host_of(url)
    signals = []
    if not host:
        return signals
    if re.fullmatch(r'\d{1,3}(?:\.\d{1,3}){3}', host):
        signals.append('The link uses a number address instead of a website name')
    if host.startswith('xn--') or '.xn--' in host or any(unicodedata.category(c).startswith('L') and ord(c) > 127 for c in host):
        signals.append('The link uses look-alike letters')
    if host in _SHORTENERS:
        signals.append('The link is shortened, so you cannot see where it goes')
    if host.rsplit('.', 1)[-1] in _ODD_TLDS:
        signals.append('The website ending is often used for scams')
    if host.count('.') >= 4:
        signals.append('The link has many parts, which can hide the real website')
    if org:
        official = OFFICIAL_DOMAINS.get(org, [])
        if not any(host == d or host.endswith('.' + d) for d in official):
            signals.append(f'The link does not belong to {org}\'s official website')
    return signals


# ── Rules: Uganda-specific scam patterns ──
RULES = [
    ('credential', 'Asks for a PIN, password or one-time code',
     r'\b(pin|otp|one[- ]time (?:code|password)|password|passcode|verification code|security code)\b'),
    ('advance_fee', 'Asks you to pay a fee first', r'\b(processing|registration|activation|verification|clearance) fee\b|\bpay (?:a |the )?(?:small )?fee\b|\bsend (?:the )?fee\b'),
    ('prize', 'Promises an unexpected prize or reward', r'\b(you (?:have )?won|winner|congratulations|prize|reward|lucky draw|free (?:data|airtime|bundle|gb))\b'),
    ('urgency', 'Pushes you to act fast', r'\b(today|tonight|now|immediately|urgent|expires?|within \d+ ?(?:hours?|minutes?)|before \d)\b'),
    ('secrecy', 'Tells you to keep it secret', r'\b(do not tell|don\'t tell|keep (?:this|it) (?:secret|private)|tell no one)\b'),
    ('money_transfer', 'Asks you to send money by Mobile Money', r'\b(send|transfer|deposit)\b.{0,40}\b(money|ugx|shs?|momo|mobile money)\b'),
    ('threat', 'Threatens you or your account', r'\b(will be (?:blocked|closed|suspended|arrested)|blocked|suspended|police|arrest)\b'),
    ('scholarship', 'Offers a scholarship or bursary', r'\b(scholarship|bursary|grant|shortlisted)\b'),
]
STRONG = {'credential', 'money_transfer'}
_SAFEGUARDING = re.compile(r'(?i)\b(kill myself|suicide|hurt myself|self[- ]harm|want to die|abuse[ds]?|naked|nude|photos? of me|blackmail|sextortion|threaten(?:ed|ing)? to (?:share|post))\b')


def rule_hits(text: str) -> list[tuple[str, str]]:
    t = text.lower()
    return [(key, label) for key, label, pattern in RULES if re.search(pattern, t)]


def needs_safeguarding(text: str) -> bool:
    return bool(_SAFEGUARDING.search(text or ''))


CATEGORY_OF = {'credential': 'otp_theft', 'advance_fee': 'advance_fee', 'scholarship': 'advance_fee',
               'prize': 'reward', 'money_transfer': 'reward', 'threat': 'otp_theft'}


def categorise(keys: set[str], url_flags: list[str], org: str | None) -> str:
    for key in ('credential', 'advance_fee', 'scholarship', 'prize', 'money_transfer', 'threat'):
        if key in keys:
            return CATEGORY_OF[key]
    if url_flags:
        return 'phishing_link'
    if org:
        return 'impersonation'
    return 'other'
