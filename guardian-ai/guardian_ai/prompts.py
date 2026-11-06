"""Prompts shared by every LLM backend (plan.md §6.6). All of them ask for JSON only."""

CLASSIFY = """You are a scam and phishing detector for messages received by children and families in Uganda
(SMS, WhatsApp, email, social media). Some values are masked as [PHONE], [EMAIL], [CODE] or [SECRET].
Judge only the message between the markers. Return ONLY JSON:
{"spamScore": <number from 0 to 1: how likely this is a scam, phishing or spam>,
 "label": "scam" | "not_scam",
 "reasons": ["short phrases naming the evidence you saw, at most 5"]}

<<<MESSAGE
{text}
MESSAGE>>>"""

EXTRACT = """You read screenshots of chats, SMS or emails that a child received. Return ONLY JSON:
{"messages": [{"side": "left" | "right" | "none", "sender_role": "other" | "child" | "unclear", "text": "..."}],
 "urls": ["..."],
 "phone_numbers_present": true | false,
 "claimed_organisation": "name or null",
 "language": "en" | "lg" | "nyn" | "other"}
How to tell senders apart in a chat screenshot: the name or number at the top is the OTHER person. Bubbles on the
LEFT side (usually white or grey) were RECEIVED from that person: "other". Bubbles on the RIGHT side (usually green
or blue) were SENT by the phone's owner, the child: "child". For an SMS or email with no bubbles, the message
is "other".
For every message first write "side": where its bubble is drawn ("left", "right", or "none" when there are no
bubbles). Look at each bubble on its own; do not assume the messages take turns.
Rules: copy message text exactly; do not judge safety; if you cannot tell who sent a message use "unclear";
never describe people's faces or bodies."""

_AUDIENCE = {
    'child': 'a Ugandan child aged {age_band}. Use short, kind, simple sentences.',
    'parent': 'a Ugandan parent or guardian. Be calm and practical, and include one tip for talking to their child.',
}

EXPLAIN = """You explain scam-check results to {audience}
Use ONLY the evidence below. Do not add new facts. Never say something is 100% safe. Never use the em dash character.
Return ONLY JSON: {{"explanation": "2-3 short sentences", "recommendedActions": ["...", "...", "..."]}}
Risk level (already decided, do not change it): {risk_level}
Evidence: {signals}"""


def classify_prompt(text: str) -> str:
    return CLASSIFY.replace('{text}', text)


def explain_prompt(risk_level: str, signals: list[str], audience: str, age_band: str) -> str:
    who = _AUDIENCE.get(audience, _AUDIENCE['child']).format(age_band=age_band)
    return EXPLAIN.format(audience=who, risk_level=risk_level, signals='; '.join(signals) or 'none recorded')
