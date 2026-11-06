from unittest import mock

from django.test import TestCase
from django.urls import reverse

from awarenessapp.models import ROLE_ANALYST, ROLE_PARENT, Users

from .models import EvaluationRun
from .services import metrics as M
from .services import screenshots
from .services.execute import create, execute

PASSWORD = 'Str0ng-pass-123'
DOWN = {'status': 'unavailable', 'meta': {'mode': 'unable_to_verify', 'error': 'guardian-ai unreachable'}}


class MetricsTests(TestCase):
    def test_binary_and_auc(self):
        m = M.binary([1, 1, 0, 0], [1, 0, 1, 0])
        self.assertEqual((m['tp'], m['fn'], m['fp'], m['tn']), (1, 1, 1, 1))
        self.assertEqual(m['f1'], 0.5)
        self.assertEqual(M.roc_auc([1, 1, 0, 0], [0.9, 0.8, 0.2, 0.1]), 1.0)
        self.assertEqual(M.roc_auc([1, 0], [0.5, 0.5]), 0.5)
        self.assertIsNone(M.roc_auc([1, 1], [0.2, 0.3]))

    def test_latency_and_threshold(self):
        self.assertEqual(M.latency([10, 20, 30])['p95_ms'], 30)
        self.assertEqual(M.best_threshold([1, 1, 0, 0], [0.9, 0.7, 0.3, 0.1]), 0.7)

    def test_screenshot_renders_png(self):
        self.assertTrue(screenshots.render(*screenshots.CASES[0]).startswith(b'\x89PNG'))


class RunTests(TestCase):
    def test_rules_only_runs_without_the_service(self):
        with mock.patch('awarenessapp.services.ai_client._call', return_value=DOWN):
            run = execute(create('rules_only'))
        self.assertEqual(run.status, EvaluationRun.STATUS_DONE)
        self.assertIn('f1', run.metrics)
        self.assertEqual(run.mode, 'rules-only')

    def test_model_down_is_recorded_as_unavailable_not_invented(self):
        with mock.patch('awarenessapp.services.ai_client._call', return_value=DOWN):
            for key in ('classifier', 'url', 'embed', 'fused', 'qwen_explain'):
                run = execute(create(key))
                self.assertEqual(run.status, EvaluationRun.STATUS_UNAVAILABLE, key)
                self.assertEqual(run.metrics, {}, key)

    def test_classifier_metrics_from_scores(self):
        def fake(method, path, **kw):
            text = kw['json']['text'].lower()
            score = 0.9 if any(w in text for w in ('pin', 'fee', 'won', 'code')) else 0.1
            return {'status': 'ok', 'spamScore': score, 'meta': {'backend': 'fake', 'host': 'test', 'mode': 'live'}}
        with mock.patch('awarenessapp.services.ai_client._call', side_effect=fake):
            run = execute(create('classifier'))
        self.assertEqual(run.status, EvaluationRun.STATUS_DONE)
        self.assertEqual(run.backend, 'fake')
        self.assertEqual(run.metrics['tp'] + run.metrics['fn'] + run.metrics['fp'] + run.metrics['tn'], run.metrics['n'])
        self.assertTrue(run.details['failures'])


class PageTests(TestCase):
    def test_analyst_only(self):
        Users.objects.create_user(email='p@x.ug', password=PASSWORD, role=ROLE_PARENT)
        self.client.login(email='p@x.ug', password=PASSWORD)
        self.assertEqual(self.client.get(reverse('evaluation_page')).status_code, 302)

    def test_page_and_detail_render(self):
        Users.objects.create_user(email='a@x.ug', password=PASSWORD, role=ROLE_ANALYST)
        self.client.login(email='a@x.ug', password=PASSWORD)
        with mock.patch('awarenessapp.services.ai_client._call', return_value=DOWN):
            run = execute(create('rules_only'))
            r = self.client.get(reverse('evaluation_page'))
        self.assertContains(r, 'Message scam classifier')
        self.assertContains(r, 'not reachable')
        self.assertContains(self.client.get(reverse('evaluation_detail', args=[run.pk])), 'Mistakes')
        self.assertEqual(self.client.get(reverse('evaluation_status')).json(), {'running': []})
