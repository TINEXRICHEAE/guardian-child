"""Client for the guardian-ai inference service (plan.md §6.8).

Every function returns the service's JSON body. Connection problems never raise: they come back as
{"status": "unavailable", "meta": {"mode": "unable_to_verify", "error": ...}} so callers can fall back to rules
and "Unable to verify" without try/except.
"""
import logging

import requests
from django.conf import settings

logger = logging.getLogger(__name__)


def _unavailable(reason: str) -> dict:
    return {'status': 'unavailable', 'meta': {'mode': 'unable_to_verify', 'backend': None, 'error': reason}}


def _call(method: str, path: str, *, timeout: int, **kwargs) -> dict:
    headers = {}
    if settings.GUARDIAN_AI_TOKEN:
        headers['X-Guardian-AI-Key'] = settings.GUARDIAN_AI_TOKEN
    url = f'{settings.GUARDIAN_AI_URL}{path}'
    try:
        r = requests.request(method, url, headers=headers, timeout=timeout, **kwargs)
    except requests.RequestException as e:
        logger.warning('guardian-ai %s %s failed: %s', method, path, type(e).__name__)
        return _unavailable(f'guardian-ai unreachable at {settings.GUARDIAN_AI_URL}')
    try:
        body = r.json()
    except ValueError:
        body = None
    if r.status_code != 200 or not isinstance(body, dict):
        detail = body.get('detail') if isinstance(body, dict) else None
        logger.warning('guardian-ai %s %s returned %s: %s', method, path, r.status_code, detail)
        return {**_unavailable(f'guardian-ai returned HTTP {r.status_code}'), 'httpStatus': r.status_code,
                'detail': detail}
    return body


def health() -> dict:
    return _call('GET', '/health', timeout=10)


def classify(text: str) -> dict:
    return _call('POST', '/classify', json={'text': text}, timeout=settings.GUARDIAN_AI_TIMEOUT)


def extract(image: bytes, mime: str, filename: str = 'upload') -> dict:
    return _call('POST', '/extract', files={'file': (filename, image, mime)},
                 timeout=settings.GUARDIAN_AI_EXTRACT_TIMEOUT)


def explain(risk_level: str, signals: list[str], *, audience: str = 'child', age_band: str = '11-13') -> dict:
    payload = {'riskLevel': risk_level, 'signals': signals, 'audience': audience, 'ageBand': age_band}
    return _call('POST', '/explain', json=payload, timeout=settings.GUARDIAN_AI_TIMEOUT)


def classify_urls(urls: list[str]) -> dict:
    """Phishing score per URL string. The service never visits the URLs."""
    return _call('POST', '/classify-url', json={'urls': urls}, timeout=settings.GUARDIAN_AI_TIMEOUT)


def embed(texts: list[str]) -> dict:
    """One normalised vector per text, for scam-wave grouping."""
    return _call('POST', '/embed', json={'texts': texts}, timeout=settings.GUARDIAN_AI_TIMEOUT)


def generate(prompt: str, *, system: str | None = None, max_tokens: int = 800, as_json: bool = False) -> dict:
    """Content generation for parent/analyst prompts (lessons, quizzes, practice emails). Never for child input."""
    payload = {'prompt': prompt, 'system': system, 'maxTokens': max_tokens, 'json': as_json}
    return _call('POST', '/generate', json=payload, timeout=settings.GUARDIAN_AI_GENERATE_TIMEOUT)
