"""Mask secrets and personal identifiers before text leaves this service for a cloud model."""
import re

_EMAIL = re.compile(r'\b[\w.+-]+@[\w-]+(?:\.[\w-]+)+\b')
# Ugandan and international mobile numbers: +256 7xx xxx xxx, 256-7xx…, 07xx xxx xxx, 0770000111
_PHONE = re.compile(r'(?<![\w+])(?:\+?256[\s-]?|0)7\d{2}[\s-]?\d{3}[\s-]?\d{3}(?!\w)')
# A secret keyword followed by its value: "PIN 1234", "OTP: 829104", "password is hunter2"
_SECRET_VALUE = re.compile(
    r'(?i)\b(pin|otp|code|password|passcode|passwd)(\s*(?:is|:|=|-)\s*|\s+)(?!\[)([^\s,.;]{3,})'
)
# Standalone 4-8 digit runs (one-time codes); amounts with separators such as 500,000 survive
_CODE = re.compile(r'(?<![\d,.])\d{4,8}(?![\d,.])')


def redact(text: str) -> str:
    text = _EMAIL.sub('[EMAIL]', text)
    text = _PHONE.sub('[PHONE]', text)
    text = _SECRET_VALUE.sub(_mask_secret, text)
    return _CODE.sub('[CODE]', text)


def _mask_secret(m: re.Match) -> str:
    value = m.group(3)
    explicit = bool(m.group(2).strip())          # "PIN: x", "password is x" vs "PIN x"
    has_digit = any(c.isdigit() for c in value)
    # "send your PIN now", "password reset link" name the secret but do not contain it
    if not has_digit and (not explicit or value.lower() in _NOT_SECRETS):
        return m.group(0)
    return f'{m.group(1)}{m.group(2)}[SECRET]'


_NOT_SECRETS = {
    'required', 'needed', 'wrong', 'incorrect', 'expired', 'invalid', 'missing', 'blocked', 'locked', 'reset',
    'below', 'above', 'here', 'sent', 'attached', 'pending',
}
