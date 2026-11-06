"""Sentence embeddings (all-MiniLM-L6-v2) for grouping similar scam messages into suspected scam waves."""
import threading
from pathlib import Path

from .base import Backend, BackendError, BackendUnavailable


class MiniLMBackend(Backend):
    name = 'minilm'
    capabilities = frozenset({'embed'})

    def __init__(self, settings):
        super().__init__(settings)
        self._lock = threading.Lock()
        self._model = None

    @property
    def model(self) -> str:
        return self.settings.embed_model_id

    @property
    def _dir(self) -> Path:
        return Path(self.settings.embed_model_dir).expanduser()

    def check(self, capability: str) -> None:
        super().check(capability)
        try:
            import sentence_transformers  # noqa: F401
        except ImportError as e:
            raise BackendUnavailable('sentence-transformers is not installed') from e
        if not (self._dir / 'model.safetensors').exists():
            raise BackendUnavailable(f'model.safetensors not found in {self._dir}')

    def embed(self, texts: list[str]) -> list[list[float]]:
        from sentence_transformers import SentenceTransformer

        with self._lock:
            if self._model is None:
                self._model = SentenceTransformer(str(self._dir), device=self.settings.embed_device)
        try:
            vectors = self._model.encode(texts, normalize_embeddings=True, convert_to_numpy=True)
        except Exception as e:
            raise BackendError(f'embedding failed: {type(e).__name__}') from e
        return [[round(float(x), 6) for x in v] for v in vectors]
