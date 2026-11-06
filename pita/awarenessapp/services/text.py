"""Text clean-up applied to everything AI models write before Guardian stores or shows it.

The em dash is built with chr(0x2014) so this file itself never contains the character.
"""
import re

EM_DASH = chr(0x2014)
_DASH = re.compile(r'\s*' + EM_DASH + r'\s*')
_DOUBLE_COMMA = re.compile(r',\s*,')
_COMMA_BEFORE_STOP = re.compile(r',\s*([.!?:;])')

NO_EM_DASH_RULE = 'Never use the em dash character; use commas, colons or full stops instead.'


def no_em_dash(value):
    """Replace em dashes with commas, recursively through dicts/lists. Other types pass through."""
    if isinstance(value, str):
        if EM_DASH not in value:
            return value
        out = _DASH.sub(', ', value)
        out = _DOUBLE_COMMA.sub(',', out)
        out = _COMMA_BEFORE_STOP.sub(r'\1', out)
        return out[2:] if out.startswith(', ') else out
    if isinstance(value, dict):
        return {k: no_em_dash(v) for k, v in value.items()}
    if isinstance(value, list):
        return [no_em_dash(v) for v in value]
    return value
