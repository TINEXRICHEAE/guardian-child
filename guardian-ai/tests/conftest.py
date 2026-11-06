import io

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from guardian_ai import chain
from guardian_ai.backends.base import Backend, BackendError, BackendUnavailable
from guardian_ai.config import Settings, get_settings
from guardian_ai.main import app


class FakeBackend(Backend):
    """Configurable stand-in for a real backend. No network."""
    name = 'fake'
    capabilities = frozenset({'classify', 'classify_url', 'embed', 'extract', 'explain', 'generate'})
    reply: dict = {}
    fail: Exception | None = None
    calls: list = []

    @property
    def model(self):
        return 'fake-model'

    def _go(self, kind, *args):
        type(self).calls.append((kind, args))
        if self.fail:
            raise self.fail
        return dict(self.reply.get(kind, {}))

    def classify(self, text):
        return self._go('classify', text)

    def extract(self, image, mime):
        return self._go('extract', image, mime)

    def explain(self, prompt):
        return self._go('explain', prompt)

    def classify_urls(self, urls):
        type(self).calls.append(('classify_url', (urls,)))
        if self.fail:
            raise self.fail
        return [{'url': u, 'phishingScore': 0.9 if 'example' in u else 0.1} for u in urls]

    def embed(self, texts):
        type(self).calls.append(('embed', (texts,)))
        if self.fail:
            raise self.fail
        return [[1.0, 0.0, 0.0] for _ in texts]

    def generate(self, prompt, *, system, max_tokens):
        type(self).calls.append(('generate', (prompt, system, max_tokens)))
        if self.fail:
            raise self.fail
        return self.reply.get('generate', '')


def make_fake(name, *, cloud=False, reply=None, fail=None, unavailable=None):
    attrs = {'name': name, 'cloud': cloud, 'reply': reply or {}, 'fail': fail, 'calls': []}
    if unavailable:
        def check(self, capability):
            raise BackendUnavailable(unavailable)
        attrs['check'] = check
    return type(f'Fake_{name}', (FakeBackend,), attrs)


@pytest.fixture
def settings(tmp_path):
    return Settings(_env_file=None, classify_backends='a,b', extract_backends='a,b', explain_backends='a,b',
                    classify_url_backends='a,b', embed_backends='a,b', generate_backends='a,b',
                    gemini_api_key='', guardian_ai_token='', inference_log=str(tmp_path / 'inference.jsonl'))


@pytest.fixture
def client(settings, monkeypatch):
    monkeypatch.setattr(chain, '_instances', {})
    app.dependency_overrides[get_settings] = lambda: settings
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.fixture
def register(monkeypatch):
    def _register(**backends):
        monkeypatch.setattr(chain, 'REGISTRY', dict(backends))
    return _register


def png_bytes(size=(40, 30)) -> bytes:
    buf = io.BytesIO()
    Image.new('RGB', size, 'white').save(buf, format='PNG')
    return buf.getvalue()


GOOD = {
    'classify': {'spamScore': 0.91, 'reasons': ['asks for PIN'], 'scoreKind': 'llm-judgement'},
    'extract': {'messages': [{'sender_role': 'other', 'text': 'You won!'}], 'urls': ['http://x.example'],
                'phone_numbers_present': False, 'claimed_organisation': 'MTN Uganda', 'language': 'en'},
    'explain': {'explanation': 'This message asks for your PIN. Real companies never do that.',
                'recommendedActions': ['Do not reply.', 'Tell a trusted adult.']},
    'generate': '{"title": "Free airtime is a trick", "quiz": []}',
}

__all__ = ['make_fake', 'png_bytes', 'GOOD', 'BackendError']
