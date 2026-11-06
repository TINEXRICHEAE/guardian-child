"""Evaluation runners, one per evaluation key (plan.md §11.5). Each calls the live guardian-ai service exactly like the
product does and returns (metrics, details, meta). Nothing is invented: when the model does not answer, the runner
raises Unavailable and the run is stored as "Model unavailable".
"""
import csv
import difflib
import json
import re
import time
from itertools import combinations
from pathlib import Path

from django.conf import settings

from awarenessapp.services import ai_client
from awarenessapp.services.text import EM_DASH
from safety.services import checks
from safety.services.analysis import assess

from . import metrics as M
from . import screenshots

DATA = Path(__file__).resolve().parent.parent / 'data'
FLAGGED = ('high', 'suspicious')
RISK_SCORE = {'high': 1.0, 'suspicious': 0.5, 'low': 0.0, 'unable_to_verify': 0.0}


class Unavailable(Exception):
    pass


def messages():
    with open(DATA / 'messages_v1.csv', encoding='utf-8') as f:
        return [{**r, 'label': int(r['label'])} for r in csv.DictReader(f)]


def _meta_of(resp):
    m = resp.get('meta') or {}
    return {'backend': m.get('backend') or '', 'model_id': m.get('model') or '', 'host': m.get('host') or '',
            'gpu': m.get('gpu') or '', 'mode': m.get('mode') or ''}


def _timed(fn, *args, **kwargs):
    t0 = time.perf_counter()
    r = fn(*args, **kwargs)
    return r, (time.perf_counter() - t0) * 1000


def _failures(rows, limit=15, score_key='score'):
    out = []
    for r in rows:
        if r['pred'] != r['label']:
            out.append({'id': r['id'], 'text': r['text'], 'category': r['category'],
                        'gold': 'scam' if r['label'] else 'legitimate',
                        'kind': 'missed scam (false negative)' if r['label'] else 'false alarm (false positive)',
                        'score': r.get(score_key), 'risk': r.get('risk')})
    return out[:limit]


# ── Message classifier on its own ──

def run_classifier(progress):
    rows, meta, lat = messages(), {}, []
    for i, r in enumerate(rows, 1):
        resp, ms = _timed(ai_client.classify, checks.redact(r['text']))
        if resp.get('status') != 'ok':
            raise Unavailable(resp.get('meta', {}).get('error') or 'the classifier did not answer')
        meta = meta or _meta_of(resp)
        r['score'] = resp['spamScore']
        lat.append(ms)
        progress(f'{i}/{len(rows)} messages')
    dev = [r for r in rows if r['split'] == 'dev']
    test = [r for r in rows if r['split'] == 'test']
    threshold = settings.CLASSIFIER_THRESHOLD
    tuned = M.best_threshold([r['label'] for r in dev], [r['score'] for r in dev])
    y, s = [r['label'] for r in test], [r['score'] for r in test]
    for r in test:
        r['pred'] = int(r['score'] >= threshold)
    headline = M.binary(y, [r['pred'] for r in test])
    tuned_m = M.binary(y, [int(x >= tuned) for x in s])
    return ({**headline, 'roc_auc': M.roc_auc(y, s), 'threshold': threshold, 'tuned_threshold': tuned,
             'f1_at_tuned': tuned_m['f1'], 'fp_at_tuned': tuned_m['fp'], 'fn_at_tuned': tuned_m['fn'],
             **M.latency(lat)},
            {'sweep': M.sweep(y, s), 'by_category': M.by_group(test, 'category'),
             'by_language': M.by_group(test, 'language'), 'failures': _failures(test),
             'note': f'Tuned threshold chosen on the dev split ({len(dev)} messages); all numbers are on the test split '
                     f'({len(test)} messages).'},
            meta)


# ── Safety rules only, and the full fused check ──

def _pipeline(progress, use_models):
    rows, meta, lat, answered = [r for r in messages() if r['split'] == 'test'], {}, [], 0
    for i, r in enumerate(rows, 1):
        a, ms = _timed(assess, checks.redact(r['text']), use_models=use_models)
        r['risk'], r['score'] = a['risk'], a['score']
        r['pred'] = int(a['risk'] in FLAGGED)
        lat.append(ms)
        if use_models:
            ok = [p for p in a['providers'].values() if p.get('mode') in ('live', 'cloud-dev')]
            answered += bool(ok)
            if ok and not meta:
                meta = {'backend': ', '.join(sorted({p.get('backend') or '' for p in a['providers'].values()})),
                        'model_id': '', 'host': ok[0].get('host') or '', 'gpu': ok[0].get('gpu') or '',
                        'mode': ok[0].get('mode') or ''}
        progress(f'{i}/{len(rows)} messages')
    if use_models and not answered:
        raise Unavailable('no model answered; this would be the same as "safety rules only"')
    if not use_models:
        meta = {'backend': 'rules', 'model_id': 'deterministic rules + fusion', 'host': 'Django', 'gpu': '', 'mode': 'rules-only'}
    y = [r['label'] for r in rows]
    risk_counts = {k: sum(r['risk'] == k for r in rows) for k in ('high', 'suspicious', 'low', 'unable_to_verify')}
    m = {**M.binary(y, [r['pred'] for r in rows]), 'roc_auc': M.roc_auc(y, [RISK_SCORE[r['risk']] for r in rows]),
         **M.latency(lat)}
    if use_models:
        m['answered_by_models'] = answered
    return (m, {'risk_levels': risk_counts, 'by_category': M.by_group(rows, 'category'),
                'by_language': M.by_group(rows, 'language'), 'failures': _failures(rows),
                'note': 'Scam = "high risk" or "some warning signs". ROC-AUC uses the risk level as an ordinal score.'},
            meta)


def run_rules_only(progress):
    return _pipeline(progress, use_models=False)


def run_fused(progress):
    return _pipeline(progress, use_models=True)


# ── Link model, with the lexical checks (its fallback) alongside ──

def run_url(progress):
    with open(DATA / 'urls_v1.csv', encoding='utf-8') as f:
        rows = [{**r, 'label': int(r['label'])} for r in csv.DictReader(f)]
    meta, lat = {}, []
    for start in range(0, len(rows), 20):
        batch = rows[start:start + 20]
        resp, ms = _timed(ai_client.classify_urls, [r['url'] for r in batch])
        if resp.get('status') != 'ok':
            raise Unavailable(resp.get('meta', {}).get('error') or 'the link model did not answer')
        meta = meta or _meta_of(resp)
        lat.append(ms / len(batch))
        for r, res in zip(batch, resp['results']):
            r['score'] = res['phishingScore']
        progress(f'{min(start + 20, len(rows))}/{len(rows)} links')
    y, s = [r['label'] for r in rows], [r['score'] for r in rows]
    for r in rows:
        r['pred'] = int(r['score'] >= 0.5)
        r['lexical'] = int(bool(checks.url_signals(r['url'], checks.claimed_organisation(r['url']))))
        r['text'], r['category'], r['id'] = r['url'], r['kind'], r['url']
    m05, m08 = M.binary(y, [r['pred'] for r in rows]), M.binary(y, [int(x >= 0.8) for x in s])
    lexical = M.binary(y, [r['lexical'] for r in rows])
    return ({**m05, 'roc_auc': M.roc_auc(y, s), 'threshold': 0.5, 'f1_at_0_8': m08['f1'], 'fp_at_0_8': m08['fp'],
             'fn_at_0_8': m08['fn'], 'lexical_f1': lexical['f1'], 'lexical_fp': lexical['fp'], 'lexical_fn': lexical['fn'],
             'mean_ms_per_url': round(sum(lat) / len(lat), 1)},
            {'sweep': M.sweep(y, s), 'by_category': M.by_group(rows, 'category'),
             'lexical_checks': lexical, 'failures': _failures(rows, 20),
             'note': 'Links are scored as text and never visited. "Lexical" is the rule-based fallback used when the model is down.'},
            meta)


# ── Embeddings: are rewordings of the same scam closer than different messages? ──

def run_embed(progress):
    data = json.loads((DATA / 'waves_v1.json').read_text(encoding='utf-8'))
    items = [(w, t) for w, texts in data['waves'].items() for t in texts] + [(None, t) for t in data['unrelated']]
    resp, ms = _timed(ai_client.embed, [t for _, t in items])
    if resp.get('status') != 'ok':
        raise Unavailable(resp.get('meta', {}).get('error') or 'the embedding model did not answer')
    vecs = resp['vectors']
    progress('comparing pairs')

    def cos(a, b):
        return sum(x * y for x, y in zip(a, b))

    y, s = [], []
    for i, j in combinations(range(len(items)), 2):
        y.append(int(items[i][0] is not None and items[i][0] == items[j][0]))
        s.append(round(cos(vecs[i], vecs[j]), 4))
    thr = M.best_threshold(y, s)
    nn_ok = 0
    wave_idx = [i for i, (w, _) in enumerate(items) if w is not None]
    for i in wave_idx:
        j = max((k for k in range(len(items)) if k != i), key=lambda k: cos(vecs[i], vecs[k]))
        nn_ok += items[j][0] == items[i][0]
    same = [x for x, t in zip(s, y) if t]
    diff = [x for x, t in zip(s, y) if not t]
    at = M.binary(y, [int(x >= thr) for x in s])
    return ({'pairs': len(y), 'mean_same_wave': round(sum(same) / len(same), 4),
             'mean_different': round(sum(diff) / len(diff), 4),
             'separation': round(sum(same) / len(same) - sum(diff) / len(diff), 4),
             'roc_auc': M.roc_auc(y, s), 'best_threshold': thr, **{k: at[k] for k in ('precision', 'recall', 'f1', 'tp', 'fp', 'tn', 'fn')},
             'nearest_neighbour_accuracy': round(nn_ok / len(wave_idx), 4), 'mean_ms': round(ms), 'dimensions': resp.get('dimensions')},
            {'sweep': M.sweep(y, s, (0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9)), 'waves': {w: len(t) for w, t in data['waves'].items()},
             'note': 'Positive pair = two rewordings of the same scam wave. Nearest-neighbour accuracy: for each wave message, '
                     'is its most similar message from the same wave?'},
            _meta_of(resp))


# ── Qwen: screenshot reading ──

def _similar(a, b):
    norm = lambda x: re.sub(r'\W+', ' ', x.lower()).strip()
    return difflib.SequenceMatcher(None, norm(a), norm(b)).ratio()


def run_qwen_extract(progress):
    meta, lat, cases, total, read_ok, role_ok, leaked, sims = {}, [], [], 0, 0, 0, 0, []
    for n, (header, truth) in enumerate(screenshots.CASES, 1):
        progress(f'screenshot {n}/{len(screenshots.CASES)}')
        resp, ms = _timed(ai_client.extract, screenshots.render(header, truth), 'image/png', f'eval-{n}.png')
        if resp.get('status') != 'ok':
            raise Unavailable(resp.get('meta', {}).get('error') or 'the vision model did not answer')
        meta = meta or _meta_of(resp)
        lat.append(ms)
        got = resp.get('messages', [])
        rows = []
        for role, text in truth:
            best = max(got, key=lambda g: _similar(text, g.get('text', '')), default=None)
            sim = _similar(text, best.get('text', '')) if best else 0.0
            matched = sim >= 0.85
            total += 1
            read_ok += matched
            role_ok += matched and best.get('sender_role') == role
            sims.append(sim)
            rows.append({'truth_role': role, 'text': text, 'read_as': best.get('text') if best else '',
                         'read_role': best.get('sender_role') if best else '', 'similarity': round(sim, 3)})
        analysed = [g.get('text', '') for g in got if g.get('sender_role') in ('other', 'unclear')]
        leak = sum(1 for r, t in truth if r == 'child' and any(_similar(t, a) >= 0.85 for a in analysed))
        leaked += leak
        cases.append({'chat': header, 'messages': rows, 'urls': resp.get('urls', []), 'child_text_analysed': leak,
                      'latency_ms': round(ms)})
    return ({'screenshots': len(screenshots.CASES), 'messages': total,
             'text_accuracy': round(read_ok / total, 4), 'mean_text_similarity': round(sum(sims) / len(sims), 4),
             'sender_role_accuracy': round(role_ok / total, 4), 'child_messages_wrongly_analysed': leaked,
             **M.latency(lat)},
            {'cases': cases,
             'note': 'Text counts as read correctly at 85% character similarity or more. Sender role must also match '
                     '("unclear" counts as wrong). Guardian analyses only messages from the other person.'},
            meta)


# ── Qwen: explanations ──

EXPLAIN_CASES = [
    ('high', ['Asks for a PIN, password or one-time code', 'Promises an unexpected prize or reward'], 'child', '11-13'),
    ('high', ['Asks you to pay a fee first', 'Offers a scholarship or bursary'], 'child', '14-17'),
    ('high', ['Asks you to send money by Mobile Money', 'Tells you to keep it secret'], 'parent', '11-13'),
    ('suspicious', ['The link does not belong to MTN Uganda\'s official website'], 'child', '8-10'),
    ('suspicious', ['Pushes you to act fast', 'The link is shortened, so you cannot see where it goes'], 'parent', '14-17'),
    ('suspicious', ['Promises an unexpected prize or reward'], 'child', '11-13'),
]
_SAFE_CLAIM = re.compile(r"(?i)\b(?:is|it's|looks|seems|totally|completely|perfectly|100%)\s+safe\b|\byou can trust\b|\bnothing to worry\b")


def _syllables(word):
    groups = re.findall(r'[aeiouy]+', word.lower())
    return max(1, len(groups) - (word.lower().endswith('e') and len(groups) > 1))


def _grade(text):
    sentences = max(1, len(re.findall(r'[.!?]+', text)))
    words = re.findall(r"[A-Za-z']+", text)
    if not words:
        return 0.0
    return round(0.39 * len(words) / sentences + 11.8 * sum(map(_syllables, words)) / len(words) - 15.59, 1)


def run_qwen_explain(progress):
    meta, lat, cases = {}, [], []
    for n, (risk, signals, audience, age) in enumerate(EXPLAIN_CASES, 1):
        progress(f'explanation {n}/{len(EXPLAIN_CASES)}')
        resp, ms = _timed(ai_client.explain, risk, signals, audience=audience, age_band=age)
        if resp.get('status') != 'ok':
            raise Unavailable(resp.get('meta', {}).get('error') or 'the language model did not answer')
        meta = meta or _meta_of(resp)
        lat.append(ms)
        text = resp.get('explanation') or ''
        actions = resp.get('recommendedActions') or []
        everything = text + ' ' + ' '.join(actions)
        checks_ = {
            'has_explanation': bool(text.strip()),
            'no_safe_claim': not _SAFE_CLAIM.search(everything),
            'no_em_dash': EM_DASH not in everything,
            'has_1_to_5_actions': 1 <= len(actions) <= 5,
            'short_sentences': len(re.findall(r"[A-Za-z']+", text)) / max(1, len(re.findall(r'[.!?]+', text))) <= 20,
        }
        cases.append({'risk': risk, 'audience': audience, 'age_band': age, 'signals': signals, 'explanation': text,
                      'actions': actions, 'grade': _grade(text), 'checks': checks_, 'latency_ms': round(ms)})
    names = list(cases[0]['checks'])
    pass_rates = {k: round(sum(c['checks'][k] for c in cases) / len(cases), 3) for k in names}
    child = [c['grade'] for c in cases if c['audience'] == 'child']
    return ({'cases': len(cases), 'all_checks_passed': sum(all(c['checks'].values()) for c in cases),
             **{f'pass_{k}': v for k, v in pass_rates.items()},
             'mean_reading_grade_child': round(sum(child) / len(child), 1) if child else None, **M.latency(lat)},
            {'cases': cases,
             'note': 'Checks run on the raw model reply. Guardian also removes em dashes and never uses the model for '
                     '"low risk" wording. Reading grade: Flesch-Kincaid estimate (lower is easier).'},
            meta)


# ── Qwen: family-version generation ──

GEN_TOPICS = [
    {'title': 'Fake free data offers', 'risk': 'Messages promise free internet bundles to get children to open a link and type their details.',
     'action': 'Do not open the link. Check offers only by dialling the official short code with a parent.', 'fmt': 'Article', 'fmt_child': 'story'},
    {'title': 'Forwarded verification codes', 'risk': 'Scammers ask children to forward a code they "sent by mistake" to take over accounts.',
     'action': 'Never forward any code. Tell a parent and block the sender.', 'fmt': 'Scenario', 'fmt_child': '"what would you do?" scenario'},
]


def run_qwen_generate(progress):
    from phishsim.services.generate import PROMPT, SYSTEM, _normalise, _safety_screen
    meta, lat, cases = {}, [], []
    for n, topic in enumerate(GEN_TOPICS, 1):
        progress(f'topic {n}/{len(GEN_TOPICS)} (about a minute each)')
        resp, ms = _timed(ai_client.generate, PROMPT.format(**topic), system=SYSTEM, as_json=True, max_tokens=2200)
        if resp.get('status') != 'ok':
            raise Unavailable(resp.get('meta', {}).get('error') or 'the language model did not answer')
        meta = meta or _meta_of(resp)
        lat.append(ms)
        data = resp.get('data')
        c = {'topic': topic['title'], 'latency_ms': round(ms), 'checks': {}, 'warnings': [], 'error': ''}
        c['checks']['valid_json'] = isinstance(data, dict)
        c['checks']['no_em_dash_raw'] = EM_DASH not in json.dumps(data or resp.get('text', ''), ensure_ascii=False)
        raw_practice = (data or {}).get('practice') if isinstance((data or {}).get('practice'), dict) else {}
        c['checks']['link_placeholder_raw'] = all(str(raw_practice.get(k, '')).count('{link}') == 1 for k in ('body', 'sms'))
        c['checks']['does_not_give_exercise_away'] = not re.search(
            r"(?i)(not real|is fake|this is a test|practice message|don'?t click|do not click)", str(raw_practice.get('body', '')))
        try:
            pack = _normalise(data or {})
            c['checks']['all_parts_present'] = True
        except ValueError as e:
            pack, c['error'] = None, str(e)
            c['checks']['all_parts_present'] = False
        if pack:
            quiz = pack['quiz']
            c['checks']['three_quiz_questions'] = len(quiz) == 3
            c['checks']['answers_marked_correctly'] = all(0 <= q['correct'] < len(q['choices']) for q in quiz)
            c['checks']['no_duplicate_questions'] = len({q['q'].strip().lower() for q in quiz}) == len(quiz)
            c['warnings'] = _safety_screen(pack)
            c['checks']['passes_safety_screen'] = not c['warnings']
            c['child_title'] = pack['child']['title']
            c['practice_subject'] = pack['practice']['subject']
        cases.append(c)
    names = sorted({k for c in cases for k in c['checks']})
    rates = {k: round(sum(c['checks'].get(k, False) for c in cases) / len(cases), 3) for k in names}
    return ({'topics': len(cases), 'all_checks_passed': sum(all(c['checks'].values()) and len(c['checks']) == len(names) for c in cases),
             **{f'pass_{k}': v for k, v in rates.items()}, **M.latency(lat)},
            {'cases': cases, 'note': 'Same prompt, clean-up and safety screen as the analyst "Family versions" page. Checks ending in "raw" '
                     'describe the model reply before Guardian repairs it (Guardian swaps an invented web address for the '
                     'practice link). Nothing is saved.'},
            meta)


RUNNERS = {
    'classifier': run_classifier, 'url': run_url, 'embed': run_embed, 'qwen_extract': run_qwen_extract,
    'qwen_explain': run_qwen_explain, 'qwen_generate': run_qwen_generate, 'rules_only': run_rules_only, 'fused': run_fused,
}
