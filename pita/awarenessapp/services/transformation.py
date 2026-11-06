import logging
import os
import json
import re
import time
from django.conf import settings
from django.utils import timezone
from . import ai_client
from .text import NO_EM_DASH_RULE, no_em_dash
from .ratelimit import RateLimitError, hit
from ..models import RawContent, AwarenessContent, Quiz, QuizQuestion, QuizChoice

logger = logging.getLogger(__name__)

_MODEL = 'gemini-3.1-flash-lite'
_FALLBACKS = [
    'gemini-2.5-flash-lite',
    'gemini-2.5-flash',
    'gemini-3-flash-preview',
]

# Rate limits for content transformation (admin-triggered)
_USER_TRANSFORMS_PER_HOUR = 30   # per admin user
_GLOBAL_TRANSFORMS_PER_DAY = 100  # total across all admins


# Rate limiting moved to services/ratelimit.py; the old names stay for existing callers.
TransformRateLimitError = RateLimitError
_rl = hit


def _generate_with_retry(client, prompt: str) -> str:
    from google.genai import errors as genai_errors
    schedule = [(_MODEL, 0), (_MODEL, 2)] + [(_fb, 0) for _fb in _FALLBACKS]
    last_exc: Exception | None = None
    for model, delay in schedule:
        if delay:
            time.sleep(delay)
        try:
            response = client.models.generate_content(model=model, contents=prompt)
            if model != _MODEL:
                logger.info("Used fallback model %s after primary quota/availability issue", model)
            return response.text
        except (genai_errors.ServerError, genai_errors.ClientError) as e:
            if e.code not in (429, 503):
                raise
            logger.warning("Gemini %d from %s - moving to next option", e.code, model)
            last_exc = e
        except Exception:
            raise
    raise last_exc


def _engagement_schema(engagement_type: str) -> str:
    """Return the exact JSON schema snippet for the chosen engagement type."""
    schemas = {
        'quiz': (
            'Generate EXACTLY 10 questions that directly test understanding of this specific topic.\n'
            'Each question must have exactly 4 answer choices ordered as A, B, C, D.\n'
            'The choices array must always have exactly 4 items in A-B-C-D order. For every choice provide:\n'
            '  - "text": the answer option text only, do NOT include an A/B/C/D prefix in the text\n'
            '    (the display labels each choice A, B, C, D automatically based on its position)\n'
            '  - "explanation": a unique, naturally worded piece of feedback.\n'
            '      * For the CORRECT choice: explain in 1-2 sentences exactly why it is right,\n'
            '        grounding the reason in the specific threat or concept being tested.\n'
            '      * For each WRONG choice: acknowledge the reasoning that might lead someone\n'
            '        there, pinpoint precisely where the thinking goes astray, and close with a\n'
            '        short motivating remark. Vary your tone and phrasing freely across questions\n'
            '        Use humour, curiosity, empathy, or encouragement as fits the context.\n'
            '        Never repeat the same closing phrase twice in the same quiz.\n'
            'The "correct" key is the 0-based index (0=A, 1=B, 2=C, 3=D) of the correct choice.\n'
            '{\n'
            '  "questions": [\n'
            '    {\n'
            '      "q": "Question text?",\n'
            '      "choices": [\n'
            '        {"text": "choice A text", "explanation": "..."},\n'
            '        {"text": "choice B text", "explanation": "..."},\n'
            '        {"text": "choice C text", "explanation": "..."},\n'
            '        {"text": "choice D text", "explanation": "..."}\n'
            '      ],\n'
            '      "correct": 0\n'
            '    },\n'
            '    ... (10 questions total)\n'
            '  ]\n'
            '}'
        ),
        'link': (
            'Provide a single real, publicly accessible URL relevant to this topic.\n'
            'First scan the RAW CONTENT above for any http/https URL, if found, use it.\n'
            'If no URL is present, identify the best authoritative public resource for Ugandan families\n'
            '(for example the Uganda Communications Commission, UNICEF Uganda or an official news article) and supply its real URL.\n'
            '{\n'
            '  "url": "https://...",\n'
            '  "label": "Descriptive link title (e.g. \'UCC: How to spot Mobile Money scams\')"\n'
            '}'
        ),
        'article': (
            'Rewrite the topic as a clear, engaging article for a Ugandan parent or guardian.\n'
            'Use plain language, short paragraphs, no jargon. Include:\n'
            '  - brief introduction explaining the threat\n'
            '  - key findings or behaviours observed\n'
            '  - how it reaches children (SMS, WhatsApp, social media, games) and what it costs families\n'
            '  - practical takeaways\n'
            'Cite the original source/author/organisation found in the RAW CONTENT, or the most\n'
            'relevant official source (UCC, Uganda Police, UNICEF, CERT) if none is identifiable.\n'
            '{\n'
            '  "summary": "Full article text (300-500 words, well-paragraphed)",\n'
            '  "source": "Name of the original organisation, author, or publication",\n'
            '  "reference_url": "URL of the original source if available, else empty string"\n'
            '}'
        ),
        'scenario': (
            'Describe a realistic situation in a Ugandan family where a child meets this scam,\n'
            'and state the correct response for the child and the parent.\n'
            '{\n'
            '  "scenario": "Realistic 3-5 sentence situation at home, at school or online",\n'
            '  "correct_action": "Clear, step-by-step correct response"\n'
            '}'
        ),
        'policy': (
            'Identify the most relevant Ugandan law, regulation or official guidance for this scam\n'
            '(e.g. the Computer Misuse Act, the Data Protection and Privacy Act, the Children Act, UCC consumer guidance).\n'
            '{\n'
            '  "policy_name": "Law or guidance + the relevant part (e.g. \'Computer Misuse Act 2011: electronic fraud\')",\n'
            '  "framework": "Full name of the law or guidance",\n'
            '  "applicability": "2-3 sentences explaining how it protects children and families from this scam",\n'
            '  "consequences": "What can happen to a child or family if the warning is ignored",\n'
            '  "remediations": "Concrete step-by-step remediation actions",\n'
            '  "reference": "Official URL of the framework document"\n'
            '}'
        ),
    }
    return schemas.get(engagement_type, schemas['article'])


def _build_prompt(raw: RawContent) -> str:
    from ..models import SCAM_CATEGORY_CHOICES
    category = dict(SCAM_CATEGORY_CHOICES).get(raw.source.threat_type, raw.source.threat_type)
    schema = _engagement_schema(raw.engagement_type)

    return f"""You write online-safety guidance for Ugandan families: parents and guardians of children aged 8 to 17.
The guidance is published by Guardian with Uganda's child online-safety regulators (the Uganda Communications
Commission, the Ministry of Gender, Labour and Social Development and the Uganda Police Child and Family Protection
Unit). Transform the raw intelligence below into a structured awareness message for parents.

SCAM CATEGORY: {category}
ENGAGEMENT TYPE (pre-selected by the analyst): {raw.engagement_type}

RAW CONTENT (extracted summary):
{raw.summary}

=== OUTPUT RULES ===
Return a single raw JSON object, NO markdown fences, NO comments, NO trailing commas.
Write for families, never for a company: do not mention employees, organisations, supervisors, security teams or
company policies. When the reader should report something, name the Uganda Police Child and Family Protection Unit,
the Uganda Communications Commission (UCC), the platform where it happened, or Sauti 116 (free child helpline).
The engagement type has already been decided: {raw.engagement_type}. Do NOT include an "engagement_type" key in your response.

Return EXACTLY this structure:
{{
  "title": "Short, clear headline for parents (max 12 words)",
  "risk": "1-2 sentences explaining concretely how this scam reaches children in Uganda and why it matters",
  "action": ["3 short, specific steps a parent and child should take", "...", "..."],
  "engagement_data": <follow the schema below exactly>
}}

=== ENGAGEMENT_DATA SCHEMA FOR: {raw.engagement_type.upper()} ===
{schema}"""


def _generate_json(prompt: str) -> tuple[dict | None, str]:
    """Generate structured content. guardian-ai first (local Qwen on the Testbed); Gemini only if explicitly allowed.

    Returns (data, provider). data is None when every provider failed.
    """
    r = ai_client.generate(prompt, as_json=True, max_tokens=3000,
                           system='You write online-safety guidance for Ugandan families. Reply with one JSON object only. ' + NO_EM_DASH_RULE)
    if r.get('status') == 'ok' and isinstance(r.get('data'), dict):
        meta = r.get('meta', {})
        return no_em_dash(r['data']), f"guardian-ai:{meta.get('backend')}@{meta.get('host')}"
    logger.warning("guardian-ai generation unavailable: %s", r.get('meta', {}).get('attempts') or r.get('meta'))

    api_key = getattr(settings, 'GEMINI_API_KEY', None) or os.environ.get('GEMINI_API_KEY')
    if not (getattr(settings, 'GUARDIAN_GEMINI_FALLBACK', False) and api_key):
        return None, ''
    try:
        from google import genai
        text = _generate_with_retry(genai.Client(api_key=api_key), prompt).strip()
        text = re.sub(r'^```[a-z]*\n?', '', text)
        text = re.sub(r'\n?```$', '', text)
        return no_em_dash(json.loads(text)), 'gemini'
    except Exception as e:
        logger.error("Gemini fallback failed: %s", e)
        return None, ''


def transform_raw_content(raw: RawContent, admin_user) -> AwarenessContent | None:
    """Turn RawContent into AwarenessContent (pending human review) using the configured AI provider."""
    # Rate limiting, enforce before any model call
    today = time.strftime('%Y-%m-%d')
    _rl(f'transform:user:{admin_user.pk}:hour', _USER_TRANSFORMS_PER_HOUR, 3600,
        f'user {admin_user.pk}/hour')
    _rl(f'transform:global:{today}', _GLOBAL_TRANSFORMS_PER_DAY, 86400,
        'global/day')

    data, provider = _generate_json(_build_prompt(raw))
    if data is None:
        logger.error("AI transformation failed for RawContent #%s", raw.pk)
        return None

    # Engagement type was set by the admin on the RawContent before transformation;
    # the model only produces engagement_data, not the type itself.
    engagement_type = raw.engagement_type
    if engagement_type not in dict(AwarenessContent.ENGAGEMENT_CHOICES):
        engagement_type = AwarenessContent.ENGAGEMENT_ARTICLE

    content = AwarenessContent.objects.create(
        raw_content=raw,
        source=raw.source,
        created_by=admin_user,
        threat_type=raw.source.threat_type,
        title=data.get('title', 'Untitled Awareness Content'),
        risk=data.get('risk', ''),
        action=_action_text(data.get('action', '')),
        engagement_type=engagement_type,
        engagement_data=data.get('engagement_data'),
        status=AwarenessContent.STATUS_PENDING,
        admin_notes=f'Generated by {provider}',
    )

    # Auto-create a Quiz model if engagement type is quiz
    if engagement_type == 'quiz':
        _create_quiz_from_data(content, data.get('engagement_data', {}), admin_user)

    raw.processed = True
    raw.save(update_fields=['processed'])
    logger.info(f"Transformed RawContent #{raw.pk} → AwarenessContent #{content.pk}")
    return content


def _action_text(value) -> str:
    """Store actions as numbered lines, whatever shape the model returned (list, list-looking text or prose)."""
    from safety.templatetags.app_ui import as_steps
    steps = as_steps(value)
    return '\n'.join(f'{i}. {step}' for i, step in enumerate(steps, 1)) if steps else str(value or '')


def _create_quiz_from_data(content: AwarenessContent, engagement_data: dict, admin_user):
    questions_data = engagement_data.get('questions', [])
    if not questions_data:
        return

    quiz = Quiz.objects.create(
        content=content,
        title=content.title,
        description=content.risk,
        created_by=admin_user,
    )

    for i, q_data in enumerate(questions_data, start=1):
        question = QuizQuestion.objects.create(
            quiz=quiz,
            question_text=q_data.get('q', f'Question {i}'),
            order=i,
        )
        choices = q_data.get('choices', [])
        correct_idx = q_data.get('correct', 0)
        for j, choice_data in enumerate(choices):
            if isinstance(choice_data, dict):
                choice_text = choice_data.get('text', '')
                explanation = choice_data.get('explanation', '')
            else:
                choice_text = str(choice_data)
                explanation = ''
            QuizChoice.objects.create(
                question=question,
                choice_text=choice_text,
                is_correct=(j == correct_idx),
                explanation=explanation,
            )
