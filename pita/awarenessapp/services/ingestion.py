import logging
import importlib.resources
import importlib.util
import os
import sys
import types
import requests
import pdfplumber
import nltk
from django.utils import timezone
from ..models import ContentSource, RawContent

# pkg_resources is not importable on Python 3.13 in some virtualenv setups,
# but sumy/breadability import it at module level. Inject a shim before sumy loads.
if 'pkg_resources' not in sys.modules:
    try:
        importlib.import_module('pkg_resources')
    except ImportError:
        import importlib.metadata as _imeta

        _shim = types.ModuleType('pkg_resources')

        def _resource_filename(package_or_req, resource_name):
            pkg = package_or_req if isinstance(package_or_req, str) else str(package_or_req)
            try:
                return str(importlib.resources.files(pkg).joinpath(resource_name))
            except Exception:
                spec = importlib.util.find_spec(pkg)
                if spec and spec.origin:
                    return os.path.join(os.path.dirname(spec.origin), resource_name)
                return resource_name

        class _Distribution:
            def __init__(self, name, version):
                self.project_name = name
                self.version = version
            def __str__(self):
                return f"{self.project_name} {self.version}"

        def _get_distribution(package_name):
            try:
                meta = _imeta.distribution(package_name)
                return _Distribution(
                    meta.metadata['Name'] or package_name,
                    meta.metadata['Version'] or '0.0.0',
                )
            except _imeta.PackageNotFoundError:
                return _Distribution(package_name, '0.0.0')

        _shim.resource_filename = _resource_filename
        _shim.get_distribution = _get_distribution
        _shim.require = lambda requirements: []
        _shim.DistributionNotFound = Exception
        _shim.VersionConflict = Exception
        sys.modules['pkg_resources'] = _shim

logger = logging.getLogger(__name__)

_SUMY_LANGUAGE = "english"
_SUMY_SENTENCES = 15
_SUMMARIZE_THRESHOLD = 5000  # chars; summarize only if raw text exceeds this


def _ensure_nltk_punkt():
    for resource in ('punkt', 'punkt_tab'):
        try:
            nltk.data.find(f'tokenizers/{resource}')
            return
        except LookupError:
            pass
    nltk.download('punkt_tab', quiet=True)


# Headers forwarded from the admin's browser to the outgoing fetch request.
_FORWARD_HEADERS = frozenset([
    'user-agent', 'accept', 'accept-language', 'accept-encoding',
    'dnt', 'upgrade-insecure-requests',
])


def _sumy_summarize_url(url: str, browser_headers: dict | None = None) -> str:
    """Fetch a URL and return a sumy LSA summary.

    browser_headers: safe subset of the admin's incoming request headers,
    forwarded so the target server sees a real browser rather than python-requests.
    """
    from sumy.parsers.html import HtmlParser
    from sumy.parsers.plaintext import PlaintextParser
    from sumy.nlp.tokenizers import Tokenizer
    from sumy.summarizers.lsa import LsaSummarizer
    from sumy.nlp.stemmers import Stemmer
    from sumy.utils import get_stop_words

    _ensure_nltk_punkt()
    stemmer = Stemmer(_SUMY_LANGUAGE)
    summarizer = LsaSummarizer(stemmer)
    summarizer.stop_words = get_stop_words(_SUMY_LANGUAGE)

    # Fetch with the admin's real browser headers so sites don't block us
    resp = requests.get(
        url,
        timeout=30,
        headers=browser_headers or {},
        allow_redirects=True,
    )
    resp.raise_for_status()

    content_type = resp.headers.get('Content-Type', '')

    if 'text/html' in content_type:
        try:
            parser = HtmlParser.from_string(resp.text, url, Tokenizer(_SUMY_LANGUAGE))
            sentences = summarizer(parser.document, _SUMY_SENTENCES)
            result = ' '.join(str(s) for s in sentences)
            if result.strip():
                return result
        except Exception as e:
            logger.warning(f"HtmlParser failed for {url}: {e}")

    # Fallback for JSON, plain-text, or failed HTML parse
    parser = PlaintextParser.from_string(resp.text[:100_000], Tokenizer(_SUMY_LANGUAGE))
    sentences = summarizer(parser.document, _SUMY_SENTENCES)
    return ' '.join(str(s) for s in sentences)


def _sumy_summarize_text(text: str) -> str:
    """Summarize plain text with sumy LSA."""
    from sumy.parsers.plaintext import PlaintextParser
    from sumy.nlp.tokenizers import Tokenizer
    from sumy.summarizers.lsa import LsaSummarizer
    from sumy.nlp.stemmers import Stemmer
    from sumy.utils import get_stop_words

    _ensure_nltk_punkt()
    parser = PlaintextParser.from_string(text, Tokenizer(_SUMY_LANGUAGE))
    stemmer = Stemmer(_SUMY_LANGUAGE)
    summarizer = LsaSummarizer(stemmer)
    summarizer.stop_words = get_stop_words(_SUMY_LANGUAGE)
    sentences = summarizer(parser.document, _SUMY_SENTENCES)
    return ' '.join(str(s) for s in sentences)


def fetch_url_source(source: ContentSource, browser_headers: dict | None = None) -> RawContent | None:
    """Fetch a URL-type source and produce a sumy summary as RawContent."""
    if not source.api_url:
        return None
    try:
        summary = _sumy_summarize_url(source.api_url, browser_headers=browser_headers)
    except Exception as e:
        logger.error(f"Failed to fetch URL source '{source.name}': {e}")
        return None

    raw = RawContent.objects.create(
        source=source,
        raw_data=source.api_url,
        summary=summary,
    )
    source.last_fetched = timezone.now()
    source.save(update_fields=['last_fetched'])
    logger.info(f"Fetched URL source '{source.name}' → RawContent #{raw.pk}")
    return raw


def _extract_text_from_document(source: ContentSource) -> str | None:
    """Return plain text from an uploaded PDF or TXT document."""
    import tempfile

    tmp_path = None
    if source.document_url:
        try:
            # PDFs are stored as Cloudinary image-type (publicly accessible).
            # TXTs are raw with access_mode='public'. Both download directly.
            resp = requests.get(source.document_url, timeout=30)
            resp.raise_for_status()
            url_clean = source.document_url.split('?')[0]
            last_segment = url_clean.rsplit('/', 1)[-1]
            ext = last_segment.rsplit('.', 1)[-1].lower() if '.' in last_segment else ''
            suffix = f'.{ext}' if ext in ('pdf', 'txt') else ''
            with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
                tmp.write(resp.content)
                tmp_path = tmp.name
        except Exception as e:
            logger.error(f"Failed to download document for '{source.name}': {e}")
            return None
        path = tmp_path
    elif source.document:
        path = source.document.path
    else:
        return None

    try:
        ext = path.rsplit('.', 1)[-1].lower()

        if ext == 'pdf':
            try:
                with pdfplumber.open(path) as pdf:
                    return '\n\n'.join(page.extract_text() or '' for page in pdf.pages)
            except Exception as e:
                logger.error(f"PDF extraction failed for '{source.name}': {e}")
                return None

        if ext == 'txt':
            try:
                with open(path, 'r', encoding='utf-8', errors='replace') as fh:
                    return fh.read()
            except Exception as e:
                logger.error(f"TXT read failed for '{source.name}': {e}")
                return None

        logger.error(f"Unsupported document extension '{ext}' for '{source.name}'")
        return None
    finally:
        if tmp_path:
            try:
                os.remove(tmp_path)
            except OSError:
                pass


def parse_document_source(source: ContentSource) -> RawContent | None:
    """Extract text from an uploaded document and persist as RawContent.

    Summarizes with sumy only when the extracted text exceeds 5000 characters.
    """
    text = _extract_text_from_document(source)
    if text is None:
        return None

    if len(text) > _SUMMARIZE_THRESHOLD:
        try:
            summary = _sumy_summarize_text(text)
        except Exception as e:
            logger.warning(f"sumy summarization failed for '{source.name}': {e}; using truncation")
            summary = text[:_SUMMARIZE_THRESHOLD]
    else:
        summary = text

    raw = RawContent.objects.create(
        source=source,
        raw_data=text,
        summary=summary,
    )
    source.last_fetched = timezone.now()
    source.save(update_fields=['last_fetched'])
    logger.info(f"Parsed document source '{source.name}' → RawContent #{raw.pk}")
    return raw


def process_prompt_source(source: ContentSource) -> RawContent | None:
    """Wrap a manual admin prompt as RawContent.

    Summarizes with sumy only when the prompt text exceeds 5000 characters.
    """
    if not source.prompt_text:
        return None

    text = source.prompt_text
    if len(text) > _SUMMARIZE_THRESHOLD:
        try:
            summary = _sumy_summarize_text(text)
        except Exception as e:
            logger.warning(f"sumy summarization failed for prompt '{source.name}': {e}; using truncation")
            summary = text[:_SUMMARIZE_THRESHOLD]
    else:
        summary = text

    raw = RawContent.objects.create(
        source=source,
        raw_data=text,
        summary=summary,
    )
    source.last_fetched = timezone.now()
    source.save(update_fields=['last_fetched'])
    logger.info(f"Processed prompt source '{source.name}' → RawContent #{raw.pk}")
    return raw


def ingest_source(source: ContentSource, browser_headers: dict | None = None) -> RawContent | None:
    """Dispatch to the correct ingestion method based on source_type."""
    if source.source_type == ContentSource.SOURCE_TYPE_URL:
        return fetch_url_source(source, browser_headers=browser_headers)

    dispatch = {
        ContentSource.SOURCE_TYPE_DOCUMENT: parse_document_source,
        ContentSource.SOURCE_TYPE_PROMPT: process_prompt_source,
    }
    handler = dispatch.get(source.source_type)
    if handler is None:
        logger.warning(f"Unknown source type '{source.source_type}' for source #{source.pk}")
        return None
    return handler(source)
