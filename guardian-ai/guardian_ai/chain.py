"""Run a capability through its configured backend chain; first success wins (plan.md §6.2)."""
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Callable

from .backends.base import Backend, BackendError
from .backends.gemini import GeminiBackend
from .backends.onnx_classifier import OnnxClassifierBackend
from .backends.minilm import MiniLMBackend
from .backends.qwen import QwenBackend
from .backends.qwen_hf import QwenHFBackend
from .backends.url_onnx import UrlOnnxBackend
from .config import Settings

logger = logging.getLogger(__name__)

REGISTRY: dict[str, type[Backend]] = {
    GeminiBackend.name: GeminiBackend,
    OnnxClassifierBackend.name: OnnxClassifierBackend,
    QwenBackend.name: QwenBackend,
    QwenHFBackend.name: QwenHFBackend,
    UrlOnnxBackend.name: UrlOnnxBackend,
    MiniLMBackend.name: MiniLMBackend,
}

_instances: dict[tuple[str, int], Backend] = {}


def get_backend(name: str, settings: Settings) -> Backend | None:
    cls = REGISTRY.get(name)
    if cls is None:
        return None
    key = (name, id(settings))
    if key not in _instances:
        _instances[key] = cls(settings)
    return _instances[key]


@dataclass
class ChainResult:
    result: dict | None = None
    backend: Backend | None = None
    attempts: list[dict] = field(default_factory=list)
    latency_ms: int = 0

    @property
    def ok(self) -> bool:
        return self.result is not None


def run(capability: str, call: Callable[[Backend], dict], settings: Settings) -> ChainResult:
    out = ChainResult()
    t0 = time.perf_counter()
    for name in settings.chain(capability):
        backend = get_backend(name, settings)
        if backend is None:
            out.attempts.append({'backend': name, 'ok': False, 'error': 'unknown backend'})
            continue
        try:
            backend.check(capability)
            out.result = call(backend)
        except BackendError as e:
            out.attempts.append({'backend': name, 'ok': False, 'error': str(e)})
            continue
        except Exception as e:      # a bug or surprise in one backend must not take down the chain
            logger.exception('backend %s crashed on %s', name, capability)
            out.attempts.append({'backend': name, 'ok': False, 'error': f'unexpected {type(e).__name__}'})
            continue
        out.backend = backend
        out.attempts.append({'backend': name, 'ok': True})
        break
    out.latency_ms = int((time.perf_counter() - t0) * 1000)
    return out


def readiness(capability: str, settings: Settings) -> list[dict[str, Any]]:
    rows = []
    for name in settings.chain(capability):
        backend = get_backend(name, settings)
        if backend is None:
            rows.append({'name': name, 'ready': False, 'reason': 'unknown backend'})
            continue
        try:
            backend.probe(capability)
            rows.append({'name': name, 'ready': True, 'cloud': backend.cloud, 'model': backend.model})
        except BackendError as e:
            rows.append({'name': name, 'ready': False, 'cloud': backend.cloud, 'reason': str(e)})
    return rows
