from unittest import mock

from django.core import mail
from django.core.cache import cache
from django.test import TestCase, override_settings
from django.urls import reverse

from awarenessapp.models import AwarenessContent, QuizAttempt, ROLE_ANALYST, ROLE_CHILD, ROLE_PARENT, Users
from phishsim.models import PracticeDelivery, TopicPack
from phishsim.services.generate import generate_pack
from safety.models import ChildProfile, ConsentRecord, GuardianChildLink, GuardianPreference, ParentAlert, Submission

PASSWORD = 'Str0ng-pass-123'
D = chr(0x2014)
GOOD = {
    'parent': {'summary': 'Children get messages promising free airtime' + D + 'then a link.', 'why': 'It steals PINs.',
               'tips': ['Ask calmly', 'Check together', 'Never share PINs']},
    'child': {'title': 'The free airtime trick', 'story': 'Amina got a message.\n\nShe asked her mum.',
              'points': ['Too good to be true', 'Rushes you'], 'action': 'Show a trusted adult.'},
    'quiz': [{'q': 'Is free airtime for a link real?', 'choices': ['Yes', 'No, it is a trick'], 'correct': 1, 'explanation': 'Scam'},
             {'q': 'Who do you tell?', 'choices': ['A trusted adult', 'Nobody'], 'correct': 0, 'explanation': 'Help'},
             {'q': 'Share your PIN?', 'choices': ['Never', 'Sometimes'], 'correct': 0, 'explanation': 'Secret'}],
    'practice': {'sender_name': 'AirtimeJoy Rewards', 'subject': 'You won 10GB free data!',
                 'body': 'Hi {name}, congratulations! You have been selected for 10GB free data. Tap {link} before midnight.',
                 'sms': 'You won 10GB! Tap {link}',
                 'red_flags': [{'label': 'Unexpected prize', 'excerpt': 'You have been selected'},
                               {'label': 'Deadline', 'excerpt': 'before midnight'}]},
}


def fake_generate(data=GOOD):
    return mock.patch('phishsim.services.generate.ai_client.generate',
                      return_value={'status': 'ok', 'data': data, 'meta': {'backend': 'qwen', 'host': 'gpu'}})


@override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend', SITE_URL='http://testserver')
class PracticeFlowTests(TestCase):
    def setUp(self):
        cache.clear()
        self.analyst = Users.objects.create_user(email='a@x.ug', password=PASSWORD, role=ROLE_ANALYST)
        self.parent = Users.objects.create_user(email='p@x.ug', password=PASSWORD, role=ROLE_PARENT)
        self.content = AwarenessContent.objects.create(created_by=self.analyst, threat_type='reward', title='Free airtime scam',
                                                       risk='Steals PINs', action='Do not click', status='approved',
                                                       engagement_type='quiz')
        self.child = ChildProfile.objects.create(nickname='Tutu', age_band='11-13', created_by=self.parent, email='tutu@x.ug')
        GuardianChildLink.objects.create(guardian=self.parent, child=self.child)

    def publish(self):
        with fake_generate():
            pack = generate_pack(self.content, user=self.analyst)
        pack.status = TopicPack.STATUS_PUBLISHED
        pack.save()
        return pack

    def turn_on_practice(self):
        self.client.login(email='p@x.ug', password=PASSWORD)
        self.client.post(reverse('child_consent', args=[self.child.pk]), {'kind': 'phishing_simulation', 'enable': '1', 'told_child': '1'})
        self.child.refresh_from_db()

    def test_generate_builds_every_version_without_em_dashes(self):
        with fake_generate():
            pack = generate_pack(self.content, user=self.analyst)
        self.assertEqual(pack.child_quiz.questions.count(), 3)
        self.assertNotIn(D, pack.parent_summary)
        self.assertEqual(pack.safety_warnings, [])
        self.assertEqual(pack.status, TopicPack.STATUS_DRAFT)

    def test_safety_screen_flags_real_brands_and_threats(self):
        bad = {**GOOD, 'practice': {**GOOD['practice'], 'sender_name': 'MTN Rewards',
                                    'body': 'Police will arrest you unless you tap {link}'}}
        with fake_generate(bad):
            pack = generate_pack(self.content, user=self.analyst)
        joined = ' '.join(pack.safety_warnings)
        self.assertIn('real organisation', joined)
        self.assertIn('banned theme', joined)

    def test_turning_on_practice_sends_welcome_notice_with_stop_link(self):
        self.turn_on_practice()
        self.assertIsNotNone(self.child.notice_sent_at)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('/stop/', mail.outbox[0].alternatives[0][0])

    def test_parent_sends_and_child_lands_on_lesson_signed_in_without_login_page(self):
        pack = self.publish()
        self.turn_on_practice()
        r = self.client.post(reverse('parent_news_detail', args=[pack.pk]), {'children': [self.child.pk]})
        self.assertEqual(r.status_code, 302)
        d = PracticeDelivery.objects.get()
        self.assertEqual(d.status, 'sent')
        email = mail.outbox[-1]
        self.assertEqual(email.extra_headers['X-Guardian-Simulation'], str(d.pk))
        self.assertIn(f'/p/{d.token}/', email.body)
        self.assertIn('Hi Tutu,', email.body)
        self.assertNotIn(D, email.body + email.alternatives[0][0])

        self.client.logout()
        r = self.client.get(reverse('practice_open', args=[d.token]))
        self.assertRedirects(r, f"{reverse('lesson', args=[pack.pk])}?d={d.pk}", fetch_redirect_response=False)
        self.child.refresh_from_db()
        self.assertEqual(self.child.user.role, ROLE_CHILD)            # passwordless child account created
        self.assertFalse(self.child.user.has_usable_password())
        page = self.client.get(r['Location'])
        self.assertContains(page, 'This was a practice message from Guardian')
        d.refresh_from_db()
        self.assertTrue(d.clicked_at and d.lesson_viewed_at)

        questions = list(pack.child_quiz.questions.prefetch_related('choices'))
        answers = {f'q{q.pk}': str(next(c for c in q.choices.all() if c.is_correct).pk) for q in questions}
        self.client.post(reverse('lesson', args=[pack.pk]), {**answers, 'd': d.pk})
        d.refresh_from_db()
        self.assertEqual((d.quiz_attempt.score, d.quiz_attempt.total), (3, 3))

        # a link-signed session cannot change the account
        self.assertEqual(self.client.post(reverse('user_profile'), '{}', content_type='application/json').status_code, 403)

    def test_link_stops_working_when_consent_is_revoked(self):
        pack = self.publish()
        self.turn_on_practice()
        self.client.post(reverse('parent_news_detail', args=[pack.pk]), {'children': [self.child.pk]})
        d = PracticeDelivery.objects.get()
        ConsentRecord.revoke(self.child, ConsentRecord.KIND_SIMULATION)
        self.client.logout()
        self.assertEqual(self.client.get(reverse('practice_open', args=[d.token])).status_code, 410)

    def test_no_practice_without_notice_or_consent(self):
        pack = self.publish()
        self.client.login(email='p@x.ug', password=PASSWORD)
        self.client.post(reverse('parent_news_detail', args=[pack.pk]), {'children': [self.child.pk]})
        d = PracticeDelivery.objects.get()
        self.assertEqual((d.status, d.skip_reason), ('skipped', 'Practice emails are turned off'))
        self.assertEqual(len(mail.outbox), 0)

    def test_stop_link_blocks_address(self):
        self.turn_on_practice()
        self.client.post(reverse('practice_stop', args=[self.child.block_token]))
        self.child.refresh_from_db()
        self.assertTrue(self.child.email_blocked)

    def test_automatic_drills_on_publish(self):
        self.turn_on_practice()
        GuardianPreference.objects.update_or_create(parent=self.parent, defaults={'auto_drills': True})
        with fake_generate():
            generate_pack(self.content, user=self.analyst)
        self.client.login(email='a@x.ug', password=PASSWORD)
        self.client.post(reverse('panel_pack', args=[self.content.pk]), {'action': 'publish'})
        d = PracticeDelivery.objects.get()
        self.assertTrue(d.automated and d.status == 'sent')

    def test_child_checking_practice_message_counts_as_report(self):
        pack = self.publish()
        self.turn_on_practice()
        self.client.post(reverse('parent_news_detail', args=[pack.pk]), {'children': [self.child.pk]})
        d = PracticeDelivery.objects.get()
        child_user = Users.objects.create_user(email='kid@x.ug', password=PASSWORD, role=ROLE_CHILD)
        self.child.user = child_user; self.child.save()
        ConsentRecord.grant(self.parent, self.child, ConsentRecord.KIND_ALERTS)
        self.client.logout(); self.client.login(email='kid@x.ug', password=PASSWORD)
        down = {'status': 'unavailable', 'meta': {}}
        with mock.patch.multiple('safety.services.analysis.ai_client', classify=mock.Mock(return_value=down),
                                 classify_urls=mock.Mock(return_value=down), explain=mock.Mock(return_value=down)):
            self.client.post(reverse('child_check'), {'content': f'You won! Tap http://testserver/p/{d.token}/ now and send your PIN'})
        d.refresh_from_db()
        sub = Submission.objects.get()
        self.assertTrue(d.reported_at)
        self.assertEqual(sub.practice_delivery, d)
        self.assertFalse(ParentAlert.objects.exists())                  # practice is not a real threat
        self.assertContains(self.client.get(reverse('child_result', args=[sub.pk])), 'Great catch')

    def test_pages_render(self):
        pack = self.publish()
        self.client.login(email='a@x.ug', password=PASSWORD)
        self.assertEqual(self.client.get(reverse('panel_pack', args=[self.content.pk])).status_code, 200)
        self.client.logout(); self.client.login(email='p@x.ug', password=PASSWORD)
        for url in (reverse('parent_news'), reverse('parent_news_detail', args=[pack.pk])):
            self.assertEqual(self.client.get(url).status_code, 200, url)
        kid = Users.objects.create_user(email='kid2@x.ug', password=PASSWORD, role=ROLE_CHILD)
        self.client.logout(); self.client.login(email='kid2@x.ug', password=PASSWORD)
        for url in (reverse('child_lessons'), reverse('lesson', args=[pack.pk])):
            self.assertEqual(self.client.get(url).status_code, 200, url)
