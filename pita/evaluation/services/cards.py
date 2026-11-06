"""Model cards for every model Guardian uses, and the evaluations that can be run for each (plan.md §11.5).

Facts here describe the Testbed deployment (guardian-ai/.env.example, scripts/start_all.sh). The live page adds what
/health reports right now, so a card never claims a model is running when it is not.
"""
from django.conf import settings

CARDS = [
    {
        'key': 'classifier',
        'name': 'Message scam classifier',
        'model_id': 'masterburator3301/distilbert-spam-phishing-classification-onnx',
        'licence': 'Not stated on the model card (declared; used for research and demonstration)',
        'capability': 'classify',
        'use': 'Gives every checked message a scam score from 0 to 1. One signal for the deterministic fusion; it never decides alone.',
        'task': 'Binary text classification: legitimate (0) vs spam/phishing (1)',
        'files': 'ONNX export of DistilBERT (distilbert-base-uncased, Apache-2.0) with its tokenizer',
        'inputs': 'Redacted text up to 5,000 characters; tokenised and padded to 512 tokens (the ONNX graph has a fixed length)',
        'runtime': 'onnxruntime on the GPU machine CPU, float32',
        'threshold': lambda: f'{settings.CLASSIFIER_THRESHOLD} (CLASSIFIER_THRESHOLD). The evaluation also suggests a tuned value from the dev split.',
        'endpoint': 'POST /classify',
        'weaknesses': 'Trained on English emails (Kaggle phishing email dataset). Short SMS-style Ugandan messages, '
                      'telco promotions and one-time-code notices are outside its training data. Scores are not calibrated.',
        'fallback': 'Deterministic rules decide alone; the result is labelled "Checked with safety rules only".',
        'evaluations': ['classifier'],
    },
    {
        'key': 'url',
        'name': 'Link phishing model',
        'model_id': 'pirocheto/phishing-url-detection',
        'licence': 'MIT (model and dataset pirocheto/phishing-url)',
        'capability': 'classify_url',
        'use': 'Scores each link found in a message. Links are analysed as text and never visited.',
        'task': 'Binary URL classification: legitimate (0) vs phishing (1)',
        'files': 'ONNX pipeline (TF-IDF character features + linear classifier)',
        'inputs': 'Up to 20 URL strings per call',
        'runtime': 'onnxruntime on the GPU machine CPU (locale attribute C.UTF-8 added to the graph)',
        'threshold': lambda: '0.8 counts as "known phishing pattern" in fusion; 0.5 adds a warning sign',
        'endpoint': 'POST /classify-url',
        'weaknesses': 'Learns from the shape of the address only. A clean-looking new domain can score low; long official URLs can score higher.',
        'fallback': 'Lexical URL checks: number addresses, look-alike letters, shorteners, unusual endings, brand vs official-domain mismatch.',
        'evaluations': ['url'],
    },
    {
        'key': 'embed',
        'name': 'Similar-message embeddings',
        'model_id': 'sentence-transformers/all-MiniLM-L6-v2',
        'licence': 'Apache-2.0',
        'capability': 'embed',
        'use': 'Turns messages into vectors so reworded copies of the same scam can be grouped into scam waves for analysts.',
        'task': 'Sentence embeddings, 384 dimensions, normalised (cosine similarity)',
        'files': 'Transformer weights and tokenizer from the Hugging Face repository',
        'inputs': 'Up to 64 texts per call; longer texts are truncated by the model (256 word pieces)',
        'runtime': 'GPU machine CPU',
        'threshold': lambda: 'Similarity threshold for "same wave" is suggested by the evaluation (best separation)',
        'endpoint': 'POST /embed',
        'weaknesses': 'Groups by topic as well as by campaign, so two different scams about prizes can look similar.',
        'fallback': 'Exact duplicate grouping by content hash.',
        'evaluations': ['embed'],
    },
    {
        'key': 'qwen',
        'name': 'Vision-language model',
        'model_id': 'Qwen/Qwen3-VL-2B-Instruct (official GGUF: Q8_0 weights + F16 vision projector)',
        'licence': 'Apache-2.0',
        'capability': 'extract',
        'use': 'Reads screenshots (which messages came from the other person), writes child and parent explanations, '
               'and writes the family versions of analyst topics. It never sets the risk level.',
        'task': 'Image + text to text (JSON for extraction and generation)',
        'files': 'Qwen3VL-2B-Instruct-Q8_0.gguf, mmproj-Qwen3VL-2B-Instruct-F16.gguf',
        'inputs': 'PNG, JPEG or WebP up to 5 MB, re-encoded with EXIF removed and the longest side at most 1600 px; context 8,192 tokens',
        'runtime': 'llama.cpp server (Hugging Face Llama app, Vulkan) on the GTX 1060 6 GB, all layers on the GPU, API key protected',
        'threshold': lambda: 'Not a classifier. Low-risk results always use fixed wording because small models over-reassure.',
        'endpoint': 'POST /extract, /explain, /generate',
        'weaknesses': 'Can mix up who sent which message in crowded screenshots, and can sound too certain. Slow for long outputs on this GPU.',
        'fallback': 'Screenshots: ask the user to paste the text. Explanations: fixed templates. Family versions: try again later '
                    '(Gemini only if GUARDIAN_GEMINI_FALLBACK is turned on).',
        'evaluations': ['qwen_extract', 'qwen_explain', 'qwen_generate'],
    },
    {
        'key': 'pipeline',
        'name': 'Safety rules and fusion',
        'model_id': 'Guardian deterministic rules (safety/services/checks.py) + fusion (analysis.py)',
        'licence': 'Team-owned code',
        'capability': None,
        'use': 'Makes the final risk decision for every check from the rules, link checks and model scores.',
        'task': 'Four results: high risk, some warning signs, low observed risk, unable to verify',
        'files': '8 Uganda-specific scam rules, URL checks, official-domain list',
        'inputs': 'Redacted text and the model signals above',
        'runtime': 'Django, no model',
        'threshold': lambda: 'Evaluated as scam = "high risk" or "some warning signs"',
        'endpoint': 'Inside Django (no network call)',
        'weaknesses': 'Keyword rules can flag genuine notices that mention PINs or codes, and miss scams written without the usual words.',
        'fallback': 'Always available. This is the safety net when every model is down.',
        'evaluations': ['rules_only', 'fused'],
    },
]

# Evaluations that can be run from the page (runner functions live in services/runners.py)
EVALUATIONS = {
    'classifier': {'title': 'Message classifier on its own', 'card': 'classifier', 'dataset': 'messages_v1 (test split)'},
    'url': {'title': 'Link model', 'card': 'url', 'dataset': 'urls_v1'},
    'embed': {'title': 'Scam-wave similarity', 'card': 'embed', 'dataset': 'waves_v1'},
    'qwen_extract': {'title': 'Screenshot reading', 'card': 'qwen', 'dataset': 'synthetic chat screenshots v1 (rendered)'},
    'qwen_explain': {'title': 'Explanation checks', 'card': 'qwen', 'dataset': 'explain cases v1'},
    'qwen_generate': {'title': 'Family-version generation checks', 'card': 'qwen', 'dataset': 'generation topics v1'},
    'rules_only': {'title': 'Safety rules only', 'card': 'pipeline', 'dataset': 'messages_v1 (test split)'},
    'fused': {'title': 'Full Guardian check (fused)', 'card': 'pipeline', 'dataset': 'messages_v1 (test split)'},
}


def card(key):
    return next(c for c in CARDS if c['key'] == key)
