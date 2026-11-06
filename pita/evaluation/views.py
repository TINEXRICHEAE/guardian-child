"""Analyst page: model cards and live, re-runnable evaluations (plan.md §11.5)."""
from django.contrib import messages
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from awarenessapp.services import ai_client
from awarenessapp.views import _require_perm

from .models import EvaluationRun
from .services.cards import CARDS, EVALUATIONS
from .services.execute import mark_stale, start_background

# Headline numbers shown on the page for each evaluation: (label, metric key, format)
HEADLINES = {
    'classifier': [('F1', 'f1', 'pct'), ('Precision', 'precision', 'pct'), ('Recall', 'recall', 'pct'),
                   ('ROC-AUC', 'roc_auc', 'num'), ('False alarms', 'fp', 'int'), ('Missed scams', 'fn', 'int'),
                   ('Mean latency', 'mean_ms', 'ms')],
    'url': [('F1', 'f1', 'pct'), ('Precision', 'precision', 'pct'), ('Recall', 'recall', 'pct'), ('ROC-AUC', 'roc_auc', 'num'),
            ('False alarms', 'fp', 'int'), ('Missed', 'fn', 'int'), ('Lexical-only F1', 'lexical_f1', 'pct')],
    'embed': [('Separation', 'separation', 'num'), ('ROC-AUC', 'roc_auc', 'num'), ('Pair F1', 'f1', 'pct'),
              ('Nearest-neighbour', 'nearest_neighbour_accuracy', 'pct'), ('Best threshold', 'best_threshold', 'num')],
    'qwen_extract': [('Text read correctly', 'text_accuracy', 'pct'), ('Sender role correct', 'sender_role_accuracy', 'pct'),
                     ('Child text analysed', 'child_messages_wrongly_analysed', 'int'), ('Mean latency', 'mean_ms', 'ms')],
    'qwen_explain': [('All checks passed', 'all_checks_passed', 'int'), ('No "safe" claims', 'pass_no_safe_claim', 'pct'),
                     ('No em dash', 'pass_no_em_dash', 'pct'), ('Child reading grade', 'mean_reading_grade_child', 'num'),
                     ('Mean latency', 'mean_ms', 'ms')],
    'qwen_generate': [('All checks passed', 'all_checks_passed', 'int'), ('Valid JSON', 'pass_valid_json', 'pct'),
                      ('Safety screen', 'pass_passes_safety_screen', 'pct'), ('Quiz answers valid', 'pass_answers_marked_correctly', 'pct'),
                      ('Mean latency', 'mean_ms', 'ms')],
    'rules_only': [('F1', 'f1', 'pct'), ('Precision', 'precision', 'pct'), ('Recall', 'recall', 'pct'),
                   ('False alarms', 'fp', 'int'), ('Missed scams', 'fn', 'int')],
    'fused': [('F1', 'f1', 'pct'), ('Precision', 'precision', 'pct'), ('Recall', 'recall', 'pct'),
              ('False alarms', 'fp', 'int'), ('Missed scams', 'fn', 'int'), ('Mean latency', 'mean_ms', 'ms')],
}


def _fmt(value, kind):
    if value is None:
        return '-'
    if kind == 'pct':
        return f'{value * 100:.1f}%'
    if kind == 'ms':
        return f'{value / 1000:.1f} s' if value >= 1000 else f'{value} ms'
    if kind == 'num':
        return f'{value:.3f}' if isinstance(value, float) else str(value)
    return str(value)


def _headline(run):
    if not run or run.status != EvaluationRun.STATUS_DONE:
        return []
    return [(label, _fmt(run.metrics.get(key), kind)) for label, key, kind in HEADLINES[run.evaluation]]


@_require_perm('view_panel')
def evaluation_page(request):
    mark_stale()
    health = ai_client.health()
    backends = health.get('backends') or {}
    latest = {}
    for run in EvaluationRun.objects.all()[:300]:
        latest.setdefault(run.evaluation, run)
    cards = []
    for c in CARDS:
        live = backends.get(c['capability']) if c['capability'] else None
        first = next((b for b in (live or []) if b.get('ready')), None)
        cards.append({
            **c, 'threshold_text': c['threshold'](),
            'live': ('Always available (Django)' if not c['capability'] else
                     f"Ready: {first['name']} ({first.get('model')})" if first else 'Not reachable right now'),
            'live_ok': not c['capability'] or bool(first),
            'evals': [{'key': k, **EVALUATIONS[k], 'run': latest.get(k), 'headline': _headline(latest.get(k))}
                      for k in c['evaluations']],
        })
    running = EvaluationRun.objects.filter(status=EvaluationRun.STATUS_RUNNING).exists()
    return render(request, 'panel/evaluation.html', {
        'cards': cards, 'health': health, 'running': running,
        'history': EvaluationRun.objects.select_related('started_by')[:40], 'titles': {k: v['title'] for k, v in EVALUATIONS.items()},
    })


@_require_perm('view_panel')
@require_POST
def evaluation_run(request):
    key = request.POST.get('evaluation', '')
    keys = list(EVALUATIONS) if key == 'all' else [key] if key in EVALUATIONS else []
    if not keys:
        messages.error(request, 'Unknown evaluation.')
    elif EvaluationRun.objects.filter(status=EvaluationRun.STATUS_RUNNING).exists():
        messages.error(request, 'An evaluation is already running. Wait for it to finish, then try again.')
    else:
        start_background(keys, request.user)
        messages.success(request, f'Started {len(keys)} evaluation{"s" if len(keys) > 1 else ""}. Results appear here as each one finishes.')
    return redirect('evaluation_page')


@_require_perm('view_panel')
def evaluation_detail(request, pk):
    run = get_object_or_404(EvaluationRun, pk=pk)
    return render(request, 'panel/evaluation_detail.html', {
        'run': run, 'meta': EVALUATIONS.get(run.evaluation, {}), 'headline': _headline(run),
        'metrics_rows': sorted(run.metrics.items()),
    })


@_require_perm('view_panel')
def evaluation_status(request):
    running = EvaluationRun.objects.filter(status=EvaluationRun.STATUS_RUNNING).order_by('started_at')
    return JsonResponse({'running': [{'id': r.pk, 'title': EVALUATIONS.get(r.evaluation, {}).get('title', r.evaluation),
                                      'progress': r.progress} for r in running]})
