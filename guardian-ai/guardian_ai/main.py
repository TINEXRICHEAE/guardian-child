"""guardian-ai: scam/phishing inference service used by Guardian's Django app (plan.md §6.3).

Every response carries `status` ("ok" | "unavailable") and `meta` (host, GPU, backend, model, latency, attempts).
Django never trusts a model to decide risk: these are signals for its deterministic fusion.
"""
import hashlib
import hmac
import re
import logging
from typing import Literal

from fastapi import Depends, FastAPI, File, Header, HTTPException, UploadFile
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from . import __version__, chain, evidence, prompts
from .backends.base import BackendError, parse_json
from .config import CAPABILITIES, Settings, get_settings
from .images import ImageRejected, prepare_image

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(name)s: %(message)s')

app = FastAPI(title='guardian-ai', version=__version__)

SENDER_ROLES = {'other', 'child', 'unclear'}
LANGUAGES = {'en', 'lg', 'nyn', 'other'}


def require_token(settings: Settings = Depends(get_settings),
                  x_guardian_ai_key: str | None = Header(default=None)) -> None:
    if settings.guardian_ai_token and not hmac.compare_digest(
            x_guardian_ai_key or '', settings.guardian_ai_token):
        raise HTTPException(401, 'missing or invalid X-Guardian-AI-Key')


# ── Output normalisation: a malformed model reply counts as a backend failure ──

def _clean_classify(data: dict, threshold: float) -> dict:
    try:
        score = float(data['spamScore'])
    except (KeyError, TypeError, ValueError) as e:
        raise BackendError('classifier reply has no numeric spamScore') from e
    score = min(max(score, 0.0), 1.0)
    reasons = [str(r) for r in (data.get('reasons') or []) if str(r).strip()][:5]
    return {'spamScore': round(score, 4), 'label': int(score >= threshold), 'threshold': threshold,
            'reasons': reasons, 'scoreKind': data.get('scoreKind', 'uncalibrated-model-score'), 'calibrated': False}


def _clean_extract(data: dict) -> dict:
    messages = []
    for m in data.get('messages') or []:
        if isinstance(m, dict) and str(m.get('text', '')).strip():
            role = m.get('sender_role') if m.get('sender_role') in SENDER_ROLES else 'unclear'
            messages.append({'sender_role': role, 'text': str(m['text'])})
    org = data.get('claimed_organisation')
    return {
        'messages': messages,
        'urls': [str(u) for u in (data.get('urls') or [])][:20],
        'phone_numbers_present': bool(data.get('phone_numbers_present')),
        'claimed_organisation': str(org) if org and str(org).lower() != 'null' else None,
        'language': data.get('language') if data.get('language') in LANGUAGES else 'other',
    }


def _clean_explain(data: dict) -> dict:
    text = str(data.get('explanation', '')).strip()
    if not text:
        raise BackendError('explanation is empty')
    low = text.lower()
    if '100%' in text and 'safe' in low:
        raise BackendError('explanation claims certainty of safety')
    if re.search(r"\b(you can trust|is safe|it'?s safe|completely safe|totally safe|safe to (?:click|open|reply|pay))\b", low) \
            and not re.search(r"\b(not|never|isn'?t|is not) (?:\w+ )?safe\b", low):
        raise BackendError('explanation claims the content is safe')
    actions = [str(a) for a in (data.get('recommendedActions') or []) if str(a).strip()][:5]
    return {'explanation': text, 'recommendedActions': actions}


# ── Response helpers ──

def _meta(res: chain.ChainResult) -> dict:
    b = res.backend
    return {
        'host': evidence.host(),
        'gpu': evidence.gpu(),
        'backend': b.name if b else None,
        'model': b.model if b else None,
        'cloud': bool(b and b.cloud),
        'mode': 'unable_to_verify' if b is None else ('cloud-dev' if b.cloud else 'live'),
        'latencyMs': res.latency_ms,
        'attempts': res.attempts,
    }


def _respond(endpoint: str, res: chain.ChainResult, settings: Settings, input_bytes: bytes) -> dict:
    meta = _meta(res)
    evidence.log_inference(settings.inference_log, {
        'endpoint': endpoint, 'status': 'ok' if res.ok else 'unavailable',
        'backend': meta['backend'], 'model': meta['model'], 'host': meta['host'], 'gpu': meta['gpu'],
        'latencyMs': meta['latencyMs'], 'inputBytes': len(input_bytes),
        'inputSha256': hashlib.sha256(input_bytes).hexdigest(),
    })
    if not res.ok:
        return {'status': 'unavailable', 'meta': meta}
    return {'status': 'ok', **res.result, 'meta': meta}


# ── Routes ──

class ClassifyIn(BaseModel):
    text: str = Field(min_length=1, max_length=5000)


class ClassifyUrlsIn(BaseModel):
    urls: list[str] = Field(min_length=1, max_length=20)


class EmbedIn(BaseModel):
    texts: list[str] = Field(min_length=1, max_length=64)


class GenerateIn(BaseModel):
    prompt: str = Field(min_length=1, max_length=20000)
    system: str | None = Field(default=None, max_length=4000)
    maxTokens: int = Field(default=800, ge=16, le=4000)
    json_output: bool = Field(default=False, alias='json')

    model_config = {'populate_by_name': True}


class ExplainIn(BaseModel):
    riskLevel: Literal['low', 'suspicious', 'high', 'unable_to_verify']
    signals: list[str] = Field(default_factory=list, max_length=20)
    audience: Literal['child', 'parent'] = 'child'
    ageBand: str = Field(default='11-13', max_length=10)


@app.get('/health')
def health(settings: Settings = Depends(get_settings)):
    backends = {cap: chain.readiness(cap, settings) for cap in CAPABILITIES}
    first_ready = [next((r for r in rows if r['ready']), None) for rows in backends.values()]
    if not any(first_ready):
        mode = 'unable_to_verify'
    else:
        mode = 'cloud-dev' if any(r and r.get('cloud') for r in first_ready) else 'live'
    return {
        'status': 'ready' if all(first_ready) else 'degraded',
        'service': 'guardian-ai',
        'version': __version__,
        'host': evidence.host(),
        'gpu': evidence.gpu(),
        'mode': mode,
        'backends': backends,
    }


@app.post('/classify', dependencies=[Depends(require_token)])
def classify(body: ClassifyIn, settings: Settings = Depends(get_settings)):
    text = body.text.strip()
    if not text:
        raise HTTPException(422, 'text is empty')
    res = chain.run('classify', lambda b: _clean_classify(b.classify(text), settings.classifier_threshold),
                    settings)
    return _respond('classify', res, settings, text.encode())


@app.post('/extract', dependencies=[Depends(require_token)])
def extract(file: UploadFile = File(...), settings: Settings = Depends(get_settings)):
    raw = file.file.read(settings.max_image_bytes + 1)
    try:
        image, mime = prepare_image(raw, max_bytes=settings.max_image_bytes, max_side=settings.max_image_side)
    except ImageRejected as e:
        return JSONResponse({'status': 'rejected', 'detail': str(e)}, status_code=e.status_code)
    res = chain.run('extract', lambda b: _clean_extract(b.extract(image, mime)), settings)
    return _respond('extract', res, settings, raw)      # the image is never written to disk


@app.post('/explain', dependencies=[Depends(require_token)])
def explain(body: ExplainIn, settings: Settings = Depends(get_settings)):
    prompt = prompts.explain_prompt(body.riskLevel, body.signals, body.audience, body.ageBand)
    res = chain.run('explain', lambda b: _clean_explain(b.explain(prompt)), settings)
    return _respond('explain', res, settings, prompt.encode())


@app.post('/classify-url', dependencies=[Depends(require_token)])
def classify_url(body: ClassifyUrlsIn, settings: Settings = Depends(get_settings)):
    """Score URL strings for phishing. URLs are never fetched or visited."""
    urls = [u.strip()[:2048] for u in body.urls if u.strip()]
    if not urls:
        raise HTTPException(422, 'no URLs')

    def call(b):
        rows = b.classify_urls(urls)
        if len(rows) != len(urls):
            raise BackendError('URL classifier returned the wrong number of results')
        return {'results': [{**r, 'label': int(r['phishingScore'] >= 0.5)} for r in rows],
                'scoreKind': 'uncalibrated-model-score', 'calibrated': False}

    res = chain.run('classify_url', call, settings)
    return _respond('classify-url', res, settings, '\n'.join(urls).encode())


@app.post('/embed', dependencies=[Depends(require_token)])
def embed(body: EmbedIn, settings: Settings = Depends(get_settings)):
    texts = [t[:settings.max_text_chars] for t in body.texts]

    def call(b):
        vectors = b.embed(texts)
        if len(vectors) != len(texts):
            raise BackendError('embedder returned the wrong number of vectors')
        return {'vectors': vectors, 'dimensions': len(vectors[0]) if vectors else 0}

    res = chain.run('embed', call, settings)
    return _respond('embed', res, settings, '\n'.join(texts).encode())


@app.post('/generate', dependencies=[Depends(require_token)])
def generate(body: GenerateIn, settings: Settings = Depends(get_settings)):
    """Content generation for parent/analyst prompts (lessons, quizzes, practice emails). Not for child input."""
    max_tokens = min(body.maxTokens, settings.max_generate_tokens)

    def call(b):
        text = (b.generate(body.prompt, system=body.system, max_tokens=max_tokens) or '').strip()
        if not text:
            raise BackendError('empty generation')
        out = {'text': text}
        if body.json_output:
            out['data'] = parse_json(text)      # invalid JSON counts as a failure, so the next backend is tried
        return out

    res = chain.run('generate', call, settings)
    return _respond('generate', res, settings, body.prompt.encode())
