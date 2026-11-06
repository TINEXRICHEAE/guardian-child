from unittest import mock

from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from awarenessapp.models import ROLE_CHILD, ROLE_PARENT, Users
from safety.models import (ChildProfile, ConsentRecord, GuardianChildLink, GuardianPreference, IncidentReport,
                           ParentAlert, Submission)
from safety.services import checks
from safety.services.analysis import _fuse

PASSWORD = 'Str0ng-pass-123'
META = {'mode': 'live', 'backend': 'fake', 'host': 'gpu'}


def fake_ai(score=0.95, url_score=0.9, extract=None, ai_down=False):
    """Patch awarenessapp.services.ai_client as used by the analysis pipeline."""
    down = {'status': 'unavailable', 'meta': {'mode': 'unable_to_verify'}}
    p = mock.patch.multiple(
        'safety.services.analysis.ai_client',
        **{'classify': mock.Mock(return_value=down if ai_down else {'status': 'ok', 'spamScore': score, 'scoreKind': 'uncalibrated-model-score', 'meta': META}),
        'classify_urls': mock.Mock(side_effect=lambda urls: down if ai_down else {'status': 'ok', 'results': [{'url': u, 'phishingScore': url_score} for u in urls], 'meta': META}),
        'explain': mock.Mock(return_value=down if ai_down else {'status': 'ok', 'explanation': 'Model explanation.', 'recommendedActions': ['Do not reply.'], 'meta': META}),
        'extract': mock.Mock(return_value=extract or down)},
    )
    return p


class ChecksTests(TestCase):
    def test_redact(self):
        self.assertEqual(checks.redact('Send PIN: 4821 to 0770 000 111 or me@x.ug'), 'Send PIN: [SECRET] to [PHONE] or [EMAIL]')
        self.assertEqual(checks.redact('Scholarship 2027, code 829104'), 'Scholarship 2027, code [CODE]')

    def test_urls_are_parsed_not_fetched(self):
        urls = checks.extract_urls('Claim at http://mtn-ug-rewards.xyz/claim.php today or www.mtn.co.ug.')
        self.assertEqual(urls, ['http://mtn-ug-rewards.xyz/claim.php', 'www.mtn.co.ug'])
        flags = checks.url_signals(urls[0], 'MTN Uganda')
        self.assertIn("The link does not belong to MTN Uganda's official website", flags)
        self.assertIn('The website ending is often used for scams', flags)
        self.assertEqual(checks.url_signals('https://www.mtn.co.ug/', 'MTN Uganda'), [])

    def test_rules_and_categories(self):
        keys = {k for k, _ in checks.rule_hits('Congratulations! You won UGX 500,000. Send your Mobile Money PIN today.')}
        self.assertTrue({'credential', 'prize', 'urgency'} <= keys)
        self.assertEqual(checks.categorise(keys, [], None), 'otp_theft')

    def test_fusion_is_deterministic(self):
        self.assertEqual(_fuse(0.97, {'credential', 'prize'}, [], [], False), ('high', False))
        self.assertEqual(_fuse(0.2, set(), [], [], False), ('low', False))
        self.assertEqual(_fuse(0.9, set(), [], [], False), ('suspicious', True))      # model alone → human review
        self.assertEqual(_fuse(None, set(), [], [], False), ('unable_to_verify', False))
        self.assertEqual(_fuse(0.6, set(), ['x'], [0.95], True), ('high', False))

    def test_safeguarding_words(self):
        self.assertTrue(checks.needs_safeguarding('he said he will share photos of me'))
        self.assertFalse(checks.needs_safeguarding('I sent money for a scholarship'))


class ChildFlowTests(TestCase):
    def setUp(self):
        cache.clear()
        self.parent = Users.objects.create_user(email='p@x.ug', password=PASSWORD, role=ROLE_PARENT)
        self.child_user = Users.objects.create_user(email='c@x.ug', password=PASSWORD, role=ROLE_CHILD)
        self.child = ChildProfile.objects.create(nickname='Kato', age_band='11-13', created_by=self.parent, user=self.child_user)
        GuardianChildLink.objects.create(guardian=self.parent, child=self.child)
        ConsentRecord.grant(self.parent, self.child, ConsentRecord.KIND_ALERTS)
        self.client.login(email='c@x.ug', password=PASSWORD)

    def test_pages_render(self):
        for name in ('child_home', 'child_check', 'child_history', 'child_report', 'child_family', 'help', 'privacy'):
            self.assertEqual(self.client.get(reverse(name)).status_code, 200, name)

    def test_high_risk_check_stores_redacted_evidence_and_alerts_parent_without_content(self):
        with fake_ai():
            r = self.client.post(reverse('child_check'), {'content': 'You won UGX 500,000! Send your Mobile Money PIN 4821 to 0770 000 111 now.'})
        sub = Submission.objects.get()
        self.assertRedirects(r, reverse('child_result', args=[sub.pk]))
        self.assertEqual(sub.risk_level, 'high')
        self.assertNotIn('4821', sub.sanitised_text)
        self.assertNotIn('0770', sub.sanitised_text)
        alert = ParentAlert.objects.get()
        self.assertEqual(alert.parent, self.parent)
        self.assertNotIn('500,000', alert.title + alert.safety_action)
        page = self.client.get(reverse('child_result', args=[sub.pk]))
        self.assertContains(page, 'Stop: this looks high risk')
        self.assertContains(page, 'Checked by Guardian AI')

    def test_no_alert_without_consent_or_preference(self):
        ConsentRecord.revoke(self.child, ConsentRecord.KIND_ALERTS)
        with fake_ai():
            self.client.post(reverse('child_check'), {'content': 'Send your PIN to claim your prize now'})
        self.assertFalse(ParentAlert.objects.exists())
        ConsentRecord.grant(self.parent, self.child, ConsentRecord.KIND_ALERTS)
        GuardianPreference.objects.update_or_create(parent=self.parent, defaults={'alert_high': False})
        with fake_ai():
            self.client.post(reverse('child_check'), {'content': 'Send your PIN to claim your prize now'})
        self.assertFalse(ParentAlert.objects.exists())

    def test_ai_down_gives_unable_to_verify_not_safe(self):
        with fake_ai(ai_down=True):
            self.client.post(reverse('child_check'), {'content': 'hello, see you at school tomorrow'})
        sub = Submission.objects.get()
        self.assertEqual(sub.risk_level, 'unable_to_verify')
        self.assertContains(self.client.get(reverse('child_result', args=[sub.pk])), 'We could not check this yet')

    def test_rules_only_result_is_labelled_honestly(self):
        with fake_ai(ai_down=True):
            self.client.post(reverse('child_check'), {'content': 'Send your Mobile Money PIN to claim your prize now'})
        sub = Submission.objects.get()
        self.assertEqual((sub.risk_level, sub.mode), ('high', 'rules-only'))
        self.assertContains(self.client.get(reverse('child_result', args=[sub.pk])), 'safety rules only')

    def test_screenshot_uses_only_received_messages_and_is_not_stored(self):
        extract = {'status': 'ok', 'meta': META, 'urls': [], 'messages': [
            {'sender_role': 'other', 'text': 'Pay UGX 35,000 processing fee today'},
            {'sender_role': 'child', 'text': 'my secret diary words'}]}
        png = b'\x89PNG\r\n\x1a\n' + b'0' * 100
        with fake_ai(extract=extract):
            self.client.post(reverse('child_check'), {'screenshot': SimpleUploadedFile('s.png', png, content_type='image/png')})
        sub = Submission.objects.get()
        self.assertEqual(sub.input_kind, 'image')
        self.assertIn('processing fee', sub.sanitised_text)
        self.assertNotIn('diary', sub.sanitised_text)
        self.assertEqual(len(sub.file_sha256), 64)

    def test_rejects_non_image_upload(self):
        r = self.client.post(reverse('child_check'), {'screenshot': SimpleUploadedFile('x.exe', b'MZ', content_type='application/octet-stream')})
        self.assertContains(r, 'Choose a PNG, JPEG or WebP')
        self.assertFalse(Submission.objects.exists())

    def test_results_are_private_to_the_submitter(self):
        with fake_ai():
            self.client.post(reverse('child_check'), {'content': 'Send your PIN now'})
        sub = Submission.objects.get()
        self.client.logout(); self.client.login(email='p@x.ug', password=PASSWORD)
        self.assertEqual(self.client.get(reverse('parent_result', args=[sub.pk])).status_code, 404)

    def test_confidential_report_never_alerts_parent(self):
        r = self.client.post(reverse('child_report'), {'category': 'money_sent', 'summary': 'I sent 35,000 for a fake bursary',
                                                       'confidential': '1', 'notify_parent': '1'})
        self.assertContains(r, 'was <strong>not</strong> told', html=False)
        rep = IncidentReport.objects.get()
        self.assertTrue(rep.confidential and not rep.notify_parent)
        self.assertEqual(rep.status, 'restricted')
        self.assertFalse(ParentAlert.objects.exists())

    def test_report_with_danger_words_is_routed_to_safeguarding(self):
        self.client.post(reverse('child_report'), {'summary': 'someone said they will share photos of me', 'notify_parent': '1'})
        rep = IncidentReport.objects.get()
        self.assertTrue(rep.needs_safeguarding and rep.confidential)
        self.assertFalse(ParentAlert.objects.exists())

    def test_report_notify_parent_sends_content_free_alert(self):
        self.client.post(reverse('child_report'), {'category': 'clicked_link', 'summary': 'I clicked a link in a fake MTN message', 'notify_parent': '1'})
        alert = ParentAlert.objects.get()
        self.assertEqual(alert.source, 'report')
        self.assertNotIn('MTN', alert.title + alert.safety_action)


class ParentPagesTests(TestCase):
    def setUp(self):
        cache.clear()
        self.parent = Users.objects.create_user(email='p@x.ug', password=PASSWORD, role=ROLE_PARENT)
        self.client.login(email='p@x.ug', password=PASSWORD)
        self.child = ChildProfile.objects.create(nickname='Amina', age_band='8-10', created_by=self.parent)
        GuardianChildLink.objects.create(guardian=self.parent, child=self.child)

    def test_pages_render(self):
        for name in ('parent_home', 'parent_alerts', 'parent_settings', 'parent_check', 'child_add'):
            self.assertEqual(self.client.get(reverse(name)).status_code, 200, name)
        self.assertEqual(self.client.get(reverse('home')).status_code, 200)

    def test_settings_save(self):
        self.client.post(reverse('parent_settings'), {'alert_high': 'on', 'protect_gambling': 'on'})
        p = GuardianPreference.objects.get(parent=self.parent)
        self.assertTrue(p.alert_high and p.protect_gambling)
        self.assertFalse(p.alert_suspicious or p.protect_fraud)

    def test_remove_child_unlinks_and_revokes(self):
        ConsentRecord.grant(self.parent, self.child, ConsentRecord.KIND_ALERTS)
        self.client.post(reverse('child_remove', args=[self.child.pk]))
        self.assertFalse(GuardianChildLink.objects.get().active)
        self.assertIsNone(ConsentRecord.active(self.child, ConsentRecord.KIND_ALERTS))
        page = self.client.get(reverse('parent_home'))
        self.assertEqual(page.context['summary']['children'], 0)
        self.assertNotContains(page, 'Age 8–10')

    def test_parent_check_uses_parent_audience(self):
        with fake_ai():
            from safety.services.analysis import ai_client
            self.client.post(reverse('parent_check'), {'content': 'Pay a processing fee today for your scholarship'})
            self.assertEqual(ai_client.explain.call_args.kwargs['audience'], 'parent')
        sub = Submission.objects.get()
        self.assertEqual(sub.submitter_role, 'parent')
        self.assertContains(self.client.get(reverse('parent_result', args=[sub.pk])), 'Talking to your child about this')


class TextCleanupTests(TestCase):
    def test_no_em_dash_anywhere_in_ai_output(self):
        from awarenessapp.services.text import no_em_dash
        d = chr(0x2014)
        self.assertEqual(no_em_dash(f'Insider threats{d}such as employees{d}can harm.'), 'Insider threats, such as employees, can harm.')
        self.assertEqual(no_em_dash({'quiz': [f'Stop {d} high risk']}), {'quiz': ['Stop, high risk']})
        self.assertEqual(no_em_dash(42), 42)

    def test_campaign_with_no_successful_sends_stays_resendable(self):
        from unittest import mock
        from awarenessapp.models import AwarenessContent, EmailCampaign, ROLE_ANALYST
        from awarenessapp.services.email_service import send_campaign
        a = Users.objects.create_user(email='an@x.ug', password=PASSWORD, role=ROLE_ANALYST)
        Users.objects.create_user(email='p@x.ug', password=PASSWORD, role=ROLE_PARENT)
        content = AwarenessContent.objects.create(created_by=a, threat_type='reward', title='T', risk='r', action='a', status='approved')
        camp = EmailCampaign.objects.create(content=content, subject='S', body_html='<p>x</p>', created_by=a)
        import ssl
        with mock.patch('django.core.mail.EmailMultiAlternatives.send', side_effect=ssl.SSLError('EOF')), \
             mock.patch('time.sleep'):
            result = send_campaign(camp)
        camp.refresh_from_db()
        self.assertEqual(result['failed'], 1)
        self.assertEqual(camp.status, EmailCampaign.STATUS_DRAFT)
