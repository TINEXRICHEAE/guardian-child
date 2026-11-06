"""Turn one approved awareness topic into every family version in a single model call (plan.md §8.0 item 1)."""
import json
import re

from django.db import transaction

from awarenessapp.models import Quiz, QuizChoice, QuizQuestion
from awarenessapp.services import ai_client
from awarenessapp.services.text import NO_EM_DASH_RULE, no_em_dash
from safety.services.checks import _BRAND_WORDS

from ..models import TopicPack

SYSTEM = ('You write online-safety material for Ugandan families: parents, and children aged 10 to 15. '
          'Reply with one JSON object only. ' + NO_EM_DASH_RULE)

PROMPT = """Turn this approved awareness topic into family material.

TOPIC TITLE: {title}
WHY IT MATTERS: {risk}
WHAT TO DO: {action}
FORMAT CHOSEN BY THE ANALYST: {fmt}

Return ONLY this JSON (all text in plain English):
{{
 "parent": {{"summary": "3-4 sentences for a parent: what this scam is and how it reaches children",
             "why": "1-2 sentences on why it matters for their child",
             "tips": ["3 short tips for talking with their child about it"]}},
 "child": {{"title": "a friendly lesson title for a child",
            "story": "a short {fmt_child} in child language, 2 short paragraphs, about a child who meets this scam",
            "points": ["3 or 4 short signs to spot"],
            "action": "1-2 sentences: what to do instead"}},
 "quiz": [{{"q": "question", "choices": ["choice A", "choice B", "choice C"], "correct": 0, "explanation": "why"}}],
 "practice": {{"sender_name": "a made-up sender name", "subject": "an email subject a child would want to open",
               "body": "a short, exciting fake message (3-5 sentences) that invites the child to tap {{link}}",
               "sms": "the same message as one SMS under 280 characters, including {{link}}",
               "red_flags": [{{"label": "the warning sign", "excerpt": "the exact words from the body that show it"}}]}}
}}

Rules:
- The quiz has exactly 3 different questions; "correct" is the 0-based index of the right choice.
- The practice message is a SAFE training message: use only made-up organisations (never MTN, Airtel, banks,
  schools or any real brand), invent web addresses ending in .example, never ask for a PIN, password or code
  directly in the message, and never use threats, fear, violence, police, exams failing, family emergencies or
  anything sexual. Use rewards, prizes, free data, game credits, scholarships or "you are selected" style hooks.
- Include {{link}} exactly once in "body" and once in "sms".
- Start "body" with "Hi {{name}}," ({{name}} is replaced with each child's own name). Do not invent a name for the reader.
- Give 3 red flags whose excerpts appear word for word in "body".
"""

_BANNED = re.compile(r'(?i)\b(police|arrest|kill|die|dead|naked|nude|sex|blackmail|threat|weapon|suicide|accident|kidnap|exam(s)? fail)\b')
_FORMATS = {'quiz': 'story', 'article': 'story', 'scenario': '"what would you do?" scenario', 'link': 'story', 'policy': 'story'}


def _safety_screen(pack: dict) -> list[str]:
    warnings = []
    practice = pack['practice']
    text = ' '.join([practice['subject'], practice['body'], practice['sms'], practice['sender_name']])
    if _BANNED.search(text):
        warnings.append(f'Practice message uses a banned theme ("{_BANNED.search(text).group(0)}").')
    for org, pattern in _BRAND_WORDS.items():
        if re.search(pattern, text.lower()):
            warnings.append(f'Practice message names a real organisation ({org}); use a made-up name.')
    if re.search(r'(?i)\b(pin|password|otp|code)\b', practice['body']) and re.search(r'(?i)\b(send|reply|enter|type)\b', practice['body']):
        warnings.append('Practice message seems to ask for a PIN, password or code; keep it to a link only.')
    for key in ('body', 'sms'):
        if practice[key].count('{link}') != 1:
            warnings.append(f'Practice {key} must contain {{link}} exactly once.')
    questions = [q['q'].strip().lower() for q in pack['quiz']]
    if len(set(questions)) != len(questions):
        warnings.append('Quiz repeats a question.')
    for i, q in enumerate(pack['quiz'], 1):
        if not (0 <= q['correct'] < len(q['choices'])):
            warnings.append(f'Quiz question {i} marks an answer that does not exist.')
    for flag in practice['red_flags']:
        if flag.get('excerpt') and flag['excerpt'] not in practice['body']:
            warnings.append(f'Red flag "{flag.get("label")}" quotes words that are not in the message.')
    return warnings


def _normalise(data: dict) -> dict:
    """Coerce the model's JSON into the expected shape; raise ValueError if it is unusable."""
    try:
        parent, child, practice = data['parent'], data['child'], data['practice']
        quiz = [q for q in data.get('quiz', []) if isinstance(q, dict) and q.get('q') and q.get('choices')]
        out = {
            'parent': {'summary': str(parent['summary']), 'why': str(parent.get('why', '')),
                       'tips': [str(t) for t in parent.get('tips', [])][:5]},
            'child': {'title': str(child['title'])[:200], 'story': str(child['story']),
                      'points': [str(p) for p in child.get('points', [])][:6], 'action': str(child.get('action', ''))},
            'quiz': [{'q': str(q['q']), 'choices': [str(c) for c in q['choices']][:4], 'correct': int(q.get('correct', 0)),
                      'explanation': str(q.get('explanation', ''))} for q in quiz][:5],
            'practice': {'sender_name': str(practice['sender_name'])[:80], 'subject': str(practice['subject'])[:160],
                         'body': str(practice['body']), 'sms': str(practice.get('sms', ''))[:320],
                         'red_flags': [{'label': str(f.get('label', '')), 'excerpt': str(f.get('excerpt', ''))}
                                       for f in practice.get('red_flags', []) if isinstance(f, dict)][:5]},
        }
    except (KeyError, TypeError, ValueError) as e:
        raise ValueError(f'the model reply is missing a part ({e})') from e
    if not out['quiz']:
        raise ValueError('the model reply has no quiz questions')
    return no_em_dash(out)


def generate_pack(content, *, user=None) -> TopicPack:
    """Create or replace the draft pack for an approved topic. Raises ValueError with a readable reason."""
    fmt = content.engagement_type or 'article'
    prompt = PROMPT.format(title=content.title, risk=content.risk, action=content.action,
                           fmt=content.get_engagement_type_display(), fmt_child=_FORMATS.get(fmt, 'story'))
    r = ai_client.generate(prompt, system=SYSTEM, as_json=True, max_tokens=2200)
    if r.get('status') != 'ok' or not isinstance(r.get('data'), dict):
        raise ValueError('Guardian AI could not write the family versions right now. Check that the GPU machine is '
                         'reachable (python manage.py ai_health) and try again.')
    data = _normalise(r['data'])
    meta = r.get('meta', {})
    with transaction.atomic():
        pack = TopicPack.objects.filter(content=content).first()
        if pack and pack.child_quiz_id:
            pack.child_quiz.delete()
        quiz = Quiz.objects.create(title=data['child']['title'], description='Child quiz for a published family topic',
                                   created_by=user or content.created_by)
        for order, q in enumerate(data['quiz'], 1):
            question = QuizQuestion.objects.create(quiz=quiz, question_text=q['q'], order=order)
            for i, choice in enumerate(q['choices']):
                QuizChoice.objects.create(question=question, choice_text=choice, is_correct=(i == q['correct']),
                                          explanation=q['explanation'] if i == q['correct'] else '')
        fields = dict(
            parent_summary=data['parent']['summary'], parent_why=data['parent']['why'], parent_tips=data['parent']['tips'],
            child_title=data['child']['title'], child_story=data['child']['story'], child_points=data['child']['points'],
            child_action=data['child']['action'], child_quiz=quiz,
            practice_sender=data['practice']['sender_name'], practice_subject=data['practice']['subject'],
            practice_body=data['practice']['body'], practice_sms=data['practice']['sms'],
            red_flags=data['practice']['red_flags'], safety_warnings=_safety_screen(data),
            status=TopicPack.STATUS_DRAFT, generated_by=f"guardian-ai:{meta.get('backend')}@{meta.get('host')}",
        )
        if pack:
            for k, v in fields.items():
                setattr(pack, k, v)
            pack.save()
        else:
            pack = TopicPack.objects.create(content=content, **fields)
    return pack


def recheck(pack: TopicPack) -> list[str]:
    """Re-run the safety screen after the analyst edits the text."""
    quiz = []
    if pack.child_quiz:
        for q in pack.child_quiz.questions.prefetch_related('choices'):
            choices = list(q.choices.all())
            correct = next((i for i, c in enumerate(choices) if c.is_correct), -1)
            quiz.append({'q': q.question_text, 'choices': [c.choice_text for c in choices], 'correct': correct})
    return _safety_screen({'quiz': quiz, 'practice': {'sender_name': pack.practice_sender, 'subject': pack.practice_subject,
                                                      'body': pack.practice_body, 'sms': pack.practice_sms,
                                                      'red_flags': pack.red_flags}})
