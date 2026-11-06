"""Families and children analytics for authorised analysts (plan.md §9, acceptance test 13).

Parents are listed by name (they receive the regulators' emails). Children appear only by pseudonym, age band and
district, never by nickname, email or anything they checked. Group totals under 5 are shown as "fewer than 5".
"""
from django.db.models import Avg, Count, Q

from ..models import ROLE_CHILD, ROLE_PARENT, QuizAttempt, Users

SUPPRESS_BELOW = 5


def families():
    from safety.models import GuardianChildLink
    parents = (Users.objects.filter(role=ROLE_PARENT).select_related('profile').annotate(
        emails_received=Count('email_deliveries', filter=Q(email_deliveries__status__in=['sent', 'opened', 'clicked']), distinct=True),
        emails_opened=Count('email_deliveries', filter=Q(email_deliveries__status__in=['opened', 'clicked']), distinct=True),
        topics_read=Count('interactions', filter=Q(interactions__viewed=True), distinct=True),
        quiz_count=Count('quiz_attempts', distinct=True),
        alerts=Count('parent_alerts', distinct=True),
        n_practice_sent=Count('practice_sent', filter=Q(practice_sent__status='sent'), distinct=True),
    ).order_by('profile__full_name', 'email'))
    children = dict(GuardianChildLink.objects.filter(active=True).values('guardian_id')
                    .annotate(n=Count('child_id', distinct=True)).values_list('guardian_id', 'n'))
    rows = []
    for p in parents:
        rows.append({'name': p.profile.display_name if hasattr(p, 'profile') else p.email, 'email': p.email,
                     'children': children.get(p.pk, 0), 'emails_received': p.emails_received, 'emails_opened': p.emails_opened,
                     'topics_read': p.topics_read, 'quiz_count': p.quiz_count, 'alerts': p.alerts,
                     'practice_sent': p.n_practice_sent, 'active': p.is_active})
    return rows


def children():
    from safety.models import ChildProfile
    kids = ChildProfile.objects.annotate(
        n_practice_sent=Count('practice_deliveries', filter=Q(practice_deliveries__status='sent'), distinct=True),
        n_practice_opened=Count('practice_deliveries', filter=Q(practice_deliveries__clicked_at__isnull=False), distinct=True),
        n_practice_spotted=Count('practice_deliveries', filter=Q(practice_deliveries__reported_at__isnull=False), distinct=True),
        n_lessons_read=Count('practice_deliveries', filter=Q(practice_deliveries__lesson_viewed_at__isnull=False), distinct=True),
        n_checks=Count('submissions', distinct=True),
        n_high_risk=Count('submissions', filter=Q(submissions__risk_level='high'), distinct=True),
        n_reports=Count('reports', distinct=True),
    ).order_by('pseudonym')
    quiz = {row['user_id']: row for row in QuizAttempt.objects.filter(user__role=ROLE_CHILD).values('user_id')
            .annotate(n=Count('id'), avg=Avg('score'), avg_total=Avg('total'))}
    rows = []
    for c in kids:
        q = quiz.get(c.user_id) if c.user_id else None
        avg_pct = round(q['avg'] * 100 / q['avg_total']) if q and q['avg_total'] else None
        rows.append({'pseudonym': c.pseudonym, 'age_band': c.get_age_band_display(), 'district': c.district or '-',
                     'device': bool(c.user_id), 'practice_sent': c.n_practice_sent, 'practice_opened': c.n_practice_opened,
                     'practice_spotted': c.n_practice_spotted, 'lessons_read': c.n_lessons_read,
                     'quiz_count': q['n'] if q else 0, 'quiz_pct': avg_pct, 'checks': c.n_checks, 'high_risk': c.n_high_risk,
                     'reports': c.n_reports})
    return rows


def _suppress(n):
    return n if n >= SUPPRESS_BELOW or n == 0 else f'fewer than {SUPPRESS_BELOW}'


def by_age_band(child_rows):
    """Children per age band, with small groups suppressed."""
    from safety.models import AGE_BANDS
    out = []
    for _, label in AGE_BANDS:
        group = [r for r in child_rows if r['age_band'] == label]
        out.append({'age_band': label, 'children': _suppress(len(group)),
                    'practice_opened': _suppress(sum(r['practice_opened'] for r in group)),
                    'checks': _suppress(sum(r['checks'] for r in group))})
    return out


def summary(family_rows, child_rows):
    sent = sum(r['practice_sent'] for r in child_rows)
    opened = sum(r['practice_opened'] for r in child_rows)
    return {
        'families': len(family_rows), 'children': len(child_rows),
        'children_with_device': sum(r['device'] for r in child_rows),
        'practice_sent': sent, 'practice_opened': opened,
        'practice_open_rate': round(opened * 100 / sent) if sent else None,
        'practice_spotted': sum(r['practice_spotted'] for r in child_rows),
        'lessons_read': sum(r['lessons_read'] for r in child_rows),
        'checks': sum(r['checks'] for r in child_rows),
        'high_risk': sum(r['high_risk'] for r in child_rows),
    }


def person_label(user):
    """How a quiz taker is shown to analysts: children by pseudonym, parents by name."""
    if user is None:
        return '-'
    if user.role == ROLE_CHILD:
        child = getattr(user, 'child_profile', None)
        return f'Child {child.pseudonym}' if child else 'Child (not linked)'
    name = user.profile.display_name if hasattr(user, 'profile') else user.email
    return f'{name} (parent)' if user.role == ROLE_PARENT else name
