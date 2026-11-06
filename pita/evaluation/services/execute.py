"""Start and record evaluation runs. Runs happen in a background thread so the page stays responsive."""
import logging
import threading
from datetime import timedelta

from django.db import close_old_connections
from django.utils import timezone

from ..models import EvaluationRun
from .cards import EVALUATIONS
from .runners import RUNNERS, Unavailable

logger = logging.getLogger(__name__)
_lock = threading.Lock()          # one evaluation at a time: the GPU machine serves one request at a time


def execute(run: EvaluationRun) -> EvaluationRun:
    """Run synchronously and save the outcome on `run`."""
    def progress(text):
        EvaluationRun.objects.filter(pk=run.pk).update(progress=text[:120])

    try:
        metrics, details, meta = RUNNERS[run.evaluation](progress)
        run.metrics, run.details, run.status = metrics, details, EvaluationRun.STATUS_DONE
        for k in ('backend', 'model_id', 'host', 'gpu', 'mode'):
            setattr(run, k, (meta.get(k) or '')[:200])
    except Unavailable as e:
        run.status, run.error = EvaluationRun.STATUS_UNAVAILABLE, str(e)
    except Exception as e:                       # recorded, never hidden
        logger.exception('Evaluation %s failed', run.evaluation)
        run.status, run.error = EvaluationRun.STATUS_FAILED, f'{type(e).__name__}: {e}'
    run.finished_at, run.progress = timezone.now(), ''
    run.save()
    return run


def create(key, user=None) -> EvaluationRun:
    return EvaluationRun.objects.create(evaluation=key, dataset=EVALUATIONS[key]['dataset'], progress='waiting for its turn',
                                        started_by=user if getattr(user, 'is_authenticated', False) else None)


def start_background(keys, user=None) -> list[EvaluationRun]:
    runs = [create(k, user) for k in keys]

    def work():
        with _lock:
            for run in runs:
                close_old_connections()
                execute(run)
            close_old_connections()

    threading.Thread(target=work, daemon=True, name='guardian-eval').start()
    return runs


def mark_stale():
    """Runs left 'running' by a server restart can never finish: record that honestly."""
    if _lock.locked():
        return
    EvaluationRun.objects.filter(status=EvaluationRun.STATUS_RUNNING,
                                 started_at__lt=timezone.now() - timedelta(minutes=30)).update(
        status=EvaluationRun.STATUS_FAILED, error='Interrupted (the server restarted during the run)',
        finished_at=timezone.now(), progress='')
