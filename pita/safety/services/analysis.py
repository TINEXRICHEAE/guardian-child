"""'Is this safe?' orchestration, version 1: text, links and screenshots (plan.md §7.4.1).

The models give signals; the deterministic `fuse()` decides the risk level. Nothing here fetches a URL, and uploaded
images are passed to guardian-ai in memory and never stored.
"""
import hashlib
import re
import time
from dataclasses import dataclass, field

from django.conf import settings

from awarenessapp.services import ai_client
from awarenessapp.services.text import no_em_dash

from ..models import ConsentRecord, GuardianPreference, ParentAlert, Submission
from . import alert_email, checks

CATEGORY_TITLES = {
    'otp_theft': 'Someone asked for a secret code or PIN', 'advance_fee': 'A fee request for a scholarship or offer',
    'reward': 'A fake prize or reward message', 'phishing_link': 'A risky link', 'impersonation': 'A message pretending to be a known organisation',
    'other': 'A suspicious message',
}
PARENT_ACTION = {
    'otp_theft': 'Remind your child never to share PINs or codes. If one was shared, change it using the official app.',
    'advance_fee': 'Check the offer together using the organisation\'s official contacts before any money is sent.',
    'reward': 'Explain that real prizes never ask for a PIN or a fee. Block the sender together.',
    'phishing_link': 'Ask your child not to open the link and to show you before signing in anywhere.',
    'impersonation': 'Contact the organisation through its official website or office, not through the message.',
    'other': 'Talk with your child about the message calmly and check it together.',
}
FALLBACK_EXPLANATION = {
    'high': 'This looks high risk. It shows strong signs of a scam.',
    'suspicious': 'Some warning signs were found. Be careful before you reply, pay or click.',
    'low': 'We did not find clear warning signs. That does not mean it is 100% safe, so still be careful.',
    'unable_to_verify': 'We could not check this right now. Do not assume it is safe.',
}
FALLBACK_ACTIONS = {
    'high': ['Do not reply, pay or share any code.', 'Block the sender.', 'Tell a trusted adult if it is safe to do so.'],
    'suspicious': ['Do not share PINs, passwords or one-time codes.', 'Check with the organisation using its official contacts.',
                   'Ask a trusted adult to look at it with you.'],
    'low': ['Still never share PINs, passwords or one-time codes.', 'If something changes or feels wrong, check again.'],
    'unable_to_verify': ['Do not share passwords, PINs or one-time codes.', 'Ask a trusted adult for help if it is safe to do so.'],
}


@dataclass
class Evidence:
    text: str = ''
    image: bytes | None = None
    mime: str = ''
    meta: dict = field(default_factory=dict)


def _fuse(score, keys, url_flags, url_scores, org_mismatch):
    """Deterministic decision. Returns (risk, needs_human_review)."""
    threshold = settings.CLASSIFIER_THRESHOLD
    strong = keys & checks.STRONG
    url_bad = any(s >= 0.8 for s in url_scores)
    evidence = len(keys) + len(url_flags) + (1 if url_bad else 0)
    if strong and (score is None or score >= threshold or evidence >= 2):
        return 'high', False
    if url_bad and (org_mismatch or (score is not None and score >= threshold)):
        return 'high', False
    if evidence >= 3 or (score is not None and score >= threshold and evidence >= 1) or org_mismatch:
        return 'suspicious', False
    if score is not None and score >= threshold:
        return 'suspicious', True                    # model says scam but no rule evidence: a human should look
    if score is None and not evidence and not url_scores:
        return 'unable_to_verify', False
    if evidence >= 1 or any(s >= 0.5 for s in url_scores):
        return 'suspicious', False
    return 'low', False


def assess(clean: str, *, use_models: bool = True) -> dict:
    """Risk decision for already-redacted text, without storing anything. Shared by checks and the evaluation page.

    use_models=False gives the 'safety rules only' result, exactly as when guardian-ai is unreachable.
    """
    providers, sources = {}, []
    # URLs and claimed organisation, parsed, never fetched
    urls = checks.extract_urls(clean)
    org = checks.claimed_organisation(clean)
    url_flags = []
    for u in urls:
        url_flags += checks.url_signals(u, org)
    org_mismatch = any('official website' in f for f in url_flags)
    url_scores = []
    if urls and use_models:
        cu = ai_client.classify_urls(urls)
        providers['classify_url'] = cu.get('meta', {})
        if cu.get('status') == 'ok':
            sources.append('url-classifier')
            url_scores = [r['phishingScore'] for r in cu['results']]
            if any(s >= 0.8 for s in url_scores):
                url_flags.append('The link looks like a known phishing pattern')
    if url_flags:
        sources.append('url-checks')

    # Message classifier
    score = None
    if clean.strip() and use_models:
        cl = ai_client.classify(clean)
        providers['classify'] = cl.get('meta', {})
        if cl.get('status') == 'ok':
            score = cl['spamScore']
            sources.append('message-classifier' if cl.get('scoreKind') != 'llm-judgement' else 'llm-classifier')

    # Rules
    hits = checks.rule_hits(clean)
    keys = {k for k, _ in hits}
    if hits:
        sources.append('rules')

    # Deterministic fusion, the LLM never sets the risk level
    risk, review = _fuse(score, keys, url_flags, url_scores, org_mismatch)
    return {
        'urls': urls, 'score': score, 'url_scores': url_scores, 'risk': risk, 'review': review,
        'category': checks.categorise(keys, url_flags, org),
        'signals': list(dict.fromkeys([label for _, label in hits] + url_flags)),
        'providers': providers, 'sources': sources,
    }


def analyse(*, user, role: str, child=None, text: str = '', image: bytes | None = None, mime: str = '',
            already_acted: bool = False) -> Submission:
    t0 = time.time()
    providers, sources = {}, []
    input_kind = 'image' if image else 'text'
    file_sha = hashlib.sha256(image).hexdigest() if image else ''

    # 1. Screenshot → text (scammer's messages only)
    if image:
        ex = ai_client.extract(image, mime, 'screenshot')
        providers['extract'] = ex.get('meta', {})
        if ex.get('status') == 'ok':
            sources.append('screenshot-extraction')
            received = [m['text'] for m in ex.get('messages', []) if m.get('sender_role') in ('other', 'unclear')]
            text = '\n'.join(received + ([text] if text.strip() else []))
            text += ''.join(f"\n{u}" for u in ex.get('urls', []) if u not in text)

    clean = checks.redact(text or '')[:5000]

    # 2-5. URLs, classifier, rules and deterministic fusion
    a = assess(clean)
    providers.update(a['providers'])
    sources += a['sources']
    urls, score, risk, review, category, signals = (a['urls'], a['score'], a['risk'], a['review'], a['category'],
                                                    a['signals'])
    if not clean.strip() and image:
        risk = 'unable_to_verify'

    # 6. Explanation for the child (or parent); templated fallback
    audience = 'parent' if role == 'parent' else 'child'
    explanation, actions = FALLBACK_EXPLANATION[risk], FALLBACK_ACTIONS[risk]
    # Low risk always uses fixed wording: small models tend to over-reassure ("this is safe, you can trust it")
    if risk not in ('unable_to_verify', 'low'):
        ex = ai_client.explain(risk, signals or ['No clear warning signs'], audience=audience,
                               age_band=getattr(child, 'age_band', '11-13'))
        providers['explain'] = ex.get('meta', {})
        if ex.get('status') == 'ok':
            explanation, actions = no_em_dash(ex['explanation']), no_em_dash(ex.get('recommendedActions') or actions)

    modes = {m.get('mode') for m in providers.values() if m.get('mode') in ('live', 'cloud-dev')}
    if risk == 'unable_to_verify':
        mode = 'unable_to_verify'
    elif not modes:
        mode = 'rules-only'          # no model answered: the result comes from Guardian's deterministic rules alone
    else:
        mode = 'cloud-dev' if 'cloud-dev' in modes else 'live'

    practice = _match_practice(child, urls) if child is not None else None
    sub = Submission.objects.create(
        practice_delivery=practice,
        submitted_by=user if getattr(user, 'is_authenticated', False) else None, submitter_role=role, child=child,
        input_kind=input_kind, file_sha256=file_sha, file_mime=mime if image else '',
        sanitised_text=clean, urls=urls, content_hash=hashlib.sha256(re.sub(r'\s+', ' ', clean.lower()).encode()).hexdigest(),
        risk_level=risk, category=category, signals=signals, evidence_sources=list(dict.fromkeys(sources)),
        classifier_score=score, explanation=explanation, recommended_actions=actions[:5], needs_human_review=review,
        already_acted=already_acted, mode=mode, providers=providers, latency_ms=int((time.time() - t0) * 1000),
        district=getattr(child, 'district', ''),
    )
    if practice is not None:
        if not practice.reported_at:
            practice.reported_at = sub.created_at
            practice.save(update_fields=['reported_at'])
        return sub                     # a practice message: no parent alert, excluded from threat intelligence
    if child is not None:
        alert_parents(child, sub)
    return sub


def _match_practice(child, urls):
    """A child checking one of their own practice messages counts as reporting it (plan.md §8.7)."""
    from phishsim.models import PracticeDelivery
    for u in urls:
        m = re.search(r'/p/([A-Za-z0-9_-]{16,64})', u)
        if m:
            d = PracticeDelivery.objects.filter(token=m.group(1), child=child).first()
            if d:
                return d
    return None


def alert_parents(child, sub: Submission) -> int:
    """Content-free alert to each linked parent who opted in, for high (or opted-in suspicious) results."""
    if sub.risk_level not in ('high', 'suspicious') or not ConsentRecord.active(child, ConsentRecord.KIND_ALERTS):
        return 0
    sent = 0
    for link in child.guardian_links.filter(active=True).select_related('guardian'):
        prefs = GuardianPreference.for_parent(link.guardian)
        if (sub.risk_level == 'high' and prefs.alert_high) or (sub.risk_level == 'suspicious' and prefs.alert_suspicious):
            alert = ParentAlert.objects.create(parent=link.guardian, child=child, severity=sub.risk_level,
                                               title=CATEGORY_TITLES.get(sub.category, CATEGORY_TITLES['other']),
                                               safety_action=PARENT_ACTION.get(sub.category, PARENT_ACTION['other']))
            alert_email.notify(alert)
            sent += 1
    return sent
