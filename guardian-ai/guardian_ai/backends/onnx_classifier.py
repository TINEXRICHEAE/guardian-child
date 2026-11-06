"""DistilBERT spam/phishing classifier via onnxruntime (Testbed mode, plan.md §6.5). Runs on CPU."""
import threading
from pathlib import Path

from .base import Backend, BackendError, BackendUnavailable


class OnnxClassifierBackend(Backend):
    name = 'onnx'
    capabilities = frozenset({'classify'})

    def __init__(self, settings):
        super().__init__(settings)
        self._lock = threading.Lock()
        self._tok = None
        self._sess = None
        self._inputs: set[str] = set()

    @property
    def model(self) -> str:
        return self.settings.classifier_model_id

    @property
    def _dir(self) -> Path:
        return Path(self.settings.classifier_dir).expanduser()

    def check(self, capability: str) -> None:
        super().check(capability)
        try:
            import onnxruntime  # noqa: F401
            import tokenizers  # noqa: F401
        except ImportError as e:
            raise BackendUnavailable(f'{e.name} is not installed') from e
        for f in ('text_classifier.onnx', 'tokenizer.json'):
            if not (self._dir / f).exists():
                raise BackendUnavailable(f'{f} not found in {self._dir}')

    def _load(self):
        with self._lock:
            if self._sess is not None:
                return
            import onnxruntime as ort
            from tokenizers import Tokenizer

            sess = ort.InferenceSession(str(self._dir / 'text_classifier.onnx'),
                                        providers=['CPUExecutionProvider'])
            self._inputs = {i.name for i in sess.get_inputs()}
            # This export has a fixed sequence length (input shape [batch, 512]): pad and truncate to it
            seq_len = sess.get_inputs()[0].shape[1]
            seq_len = seq_len if isinstance(seq_len, int) else 512
            tok = Tokenizer.from_file(str(self._dir / 'tokenizer.json'))
            tok.enable_truncation(seq_len)
            tok.enable_padding(length=seq_len, pad_id=tok.token_to_id('[PAD]') or 0, pad_token='[PAD]')
            self._tok, self._sess = tok, sess

    def classify(self, text: str) -> dict:
        import numpy as np

        self._load()
        enc = self._tok.encode(text)
        feed = {
            'input_ids': np.array([enc.ids], dtype=np.int64),
            'attention_mask': np.array([enc.attention_mask], dtype=np.int64),
        }
        try:
            out = self._sess.run(None, {k: v for k, v in feed.items() if k in self._inputs})[0][0]
        except Exception as e:
            raise BackendError(f'onnx inference failed: {type(e).__name__}') from e
        out = np.asarray(out, dtype=np.float64)
        if out.shape != (2,):
            raise BackendError(f'unexpected classifier output shape {out.shape}')
        if not (np.all(out >= 0) and abs(out.sum() - 1) < 1e-3):   # logits, not probabilities
            out = np.exp(out - out.max())
            out /= out.sum()
        return {'spamScore': float(out[1]), 'reasons': [], 'scoreKind': 'uncalibrated-model-score'}
