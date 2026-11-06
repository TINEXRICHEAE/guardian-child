"""Run evaluations from the terminal and optionally save the results as Testbed evidence.

    python manage.py run_eval                      # all evaluations
    python manage.py run_eval classifier fused     # chosen ones
    python manage.py run_eval --out ../docs/testbed-evidence/2026-11-06_evaluation.json
"""
import json

from django.core.management.base import BaseCommand, CommandError

from evaluation.services.cards import EVALUATIONS
from evaluation.services.execute import create, execute


class Command(BaseCommand):
    help = 'Run model evaluations against the live guardian-ai service and store them as EvaluationRun rows.'

    def add_arguments(self, parser):
        parser.add_argument('evaluations', nargs='*', help=f'any of: {", ".join(EVALUATIONS)}')
        parser.add_argument('--out', help='write the results to this JSON file')

    def handle(self, *args, **opts):
        keys = opts['evaluations'] or list(EVALUATIONS)
        unknown = [k for k in keys if k not in EVALUATIONS]
        if unknown:
            raise CommandError(f'unknown evaluation(s): {", ".join(unknown)}')
        results = []
        for key in keys:
            self.stdout.write(f'{EVALUATIONS[key]["title"]} ... ', ending='')
            self.stdout.flush()
            run = execute(create(key))
            self.stdout.write(f'{run.get_status_display()} in {run.duration_s} s'
                              + (f' ({run.error})' if run.error else ''))
            if run.status == 'done':
                shown = {k: v for k, v in run.metrics.items() if k in ('f1', 'precision', 'recall', 'fp', 'fn', 'roc_auc',
                                                                      'text_accuracy', 'sender_role_accuracy', 'separation',
                                                                      'all_checks_passed', 'mean_ms')}
                self.stdout.write(f'    {shown}  backend={run.backend} host={run.host}')
            results.append({'id': run.pk, 'evaluation': key, 'status': run.status, 'dataset': run.dataset,
                            'backend': run.backend, 'model': run.model_id, 'host': run.host, 'gpu': run.gpu,
                            'mode': run.mode, 'started_at': run.started_at.isoformat(), 'duration_s': run.duration_s,
                            'metrics': run.metrics, 'details': run.details, 'error': run.error})
        if opts['out']:
            with open(opts['out'], 'w', encoding='utf-8') as f:
                json.dump(results, f, indent=2, ensure_ascii=False)
            self.stdout.write(self.style.SUCCESS(f'Saved {len(results)} result(s) to {opts["out"]}'))
