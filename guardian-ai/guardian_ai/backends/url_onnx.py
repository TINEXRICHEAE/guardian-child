"""URL phishing classifier (pirocheto/phishing-url-detection, ONNX, MIT). Judges the URL string only; never visits it."""
import threading
from pathlib import Path

from .base import Backend, BackendError, BackendUnavailable


class UrlOnnxBackend(Backend):
    name = 'url-onnx'
    capabilities = frozenset({'classify_url'})

    def __init__(self, settings):
        super().__init__(settings)
        self._lock = threading.Lock()
        self._sess = None

    @property
    def model(self) -> str:
        return self.settings.url_classifier_model_id

    @property
    def _path(self) -> Path:
        return Path(self.settings.url_classifier_dir).expanduser() / 'model.onnx'

    def check(self, capability: str) -> None:
        super().check(capability)
        try:
            import onnxruntime  # noqa: F401
        except ImportError as e:
            raise BackendUnavailable('onnxruntime is not installed') from e
        if not self._path.exists():
            raise BackendUnavailable(f'model.onnx not found in {self._path.parent}')

    def _load(self):
        import onnxruntime as ort

        model = str(self._path)
        try:
            import onnx
        except ImportError:
            onnx = None
        if onnx is not None:
            # The export's StringNormalizer has no locale attribute, so onnxruntime defaults to en_US.UTF-8, which
            # minimal Linux/WSL images lack (installing it needs root). Lower-casing URLs is identical under
            # C.UTF-8, so set the locale explicitly at load time.
            proto = onnx.load(model)
            locale = self.settings.url_classifier_locale
            for node in proto.graph.node:
                if node.op_type != 'StringNormalizer':
                    continue
                existing = [a for a in node.attribute if a.name == 'locale']
                if existing:
                    existing[0].s = locale.encode()
                else:
                    node.attribute.append(onnx.helper.make_attribute('locale', locale))
            model = proto.SerializeToString()
        try:
            self._sess = ort.InferenceSession(model, providers=['CPUExecutionProvider'])
        except Exception as e:
            hint = '' if onnx else ' (pip install onnx so the locale can be switched)'
            raise BackendUnavailable(f'url classifier failed to load: {type(e).__name__}{hint}') from e

    def classify_urls(self, urls: list[str]) -> list[dict]:
        import numpy as np

        with self._lock:
            if self._sess is None:
                self._load()
        try:
            probs = self._sess.run(None, {'inputs': np.array(urls, dtype='str')})[1]
        except Exception as e:
            raise BackendError(f'url classifier failed: {type(e).__name__}') from e
        return [{'url': u, 'phishingScore': round(float(p[1]), 4)} for u, p in zip(urls, probs)]
