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
        r = self.client.post(reverse('parent_news_detail', args=[pack.content_id]), {'children': [self.child.pk]})
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

    @override_settings(GUARDIAN_PRACTICE_OPEN=False)
    def test_link_stops_working_when_consent_is_revoked(self):
        pack = self.publish()
        self.turn_on_practice()
        self.client.post(reverse('parent_news_detail', args=[pack.content_id]), {'children': [self.child.pk]})
        d = PracticeDelivery.objects.get()
        ConsentRecord.revoke(self.child, ConsentRecord.KIND_SIMULATION)
        self.client.logout()
        self.assertEqual(self.client.get(reverse('practice_open', args=[d.token])).status_code, 410)

    @override_settings(GUARDIAN_PRACTICE_OPEN=False)
    def test_no_practice_without_notice_or_consent(self):
        pack = self.publish()
        self.client.login(email='p@x.ug', password=PASSWORD)
        self.client.post(reverse('parent_news_detail', args=[pack.content_id]), {'children': [self.child.pk]})
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
        self.client.post(reverse('parent_news_detail', args=[pack.content_id]), {'children': [self.child.pk]})
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
        for url in (reverse('parent_news'), reverse('parent_news_detail', args=[pack.content_id])):
            self.assertEqual(self.client.get(url).status_code, 200, url)
        kid = Users.objects.create_user(email='kid2@x.ug', password=PASSWORD, role=ROLE_CHILD)
        self.client.logout(); self.client.login(email='kid2@x.ug', password=PASSWORD)
        for url in (reverse('child_lessons'), reverse('lesson', args=[pack.pk])):
            self.assertEqual(self.client.get(url).status_code, 200, url)


@override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend', SITE_URL='http://testserver')
class FamilyLibraryTests(TestCase):
    """The parent library: news list, topic page, quiz, sending, and the old library and email leading there."""

    def setUp(self):
        cache.clear()
        self.analyst = Users.objects.create_user(email='a@x.ug', password=PASSWORD, role=ROLE_ANALYST)
        self.parent = Users.objects.create_user(email='p@x.ug', password=PASSWORD, role=ROLE_PARENT)
        self.content = AwarenessContent.objects.create(
            created_by=self.analyst, threat_type='reward', title='Free airtime scam', risk='Steals PINs',
            action="['Do not click the link.', 'Show a parent.']", status='approved', engagement_type='article',
            engagement_data={'summary': 'Scammers promise airtime.'})
        self.client.login(email='p@x.ug', password=PASSWORD)

    def test_topic_without_family_version_is_listed_and_readable(self):
        r = self.client.get(reverse('parent_news'))
        self.assertContains(r, 'Free airtime scam')
        self.assertNotContains(r, 'coming soon')
        page = self.client.get(reverse('parent_news_detail', args=[self.content.pk]))
        self.assertContains(page, 'Scammers promise airtime.')
        self.assertContains(page, '<li>Do not click the link.</li>', html=True)       # no raw ['...'] list
        self.assertNotContains(page, "['Do not")
        self.assertContains(page, 'Ask for the child version')
        r = self.client.get(reverse('parent_news'))
        self.assertContains(r, 'Already read (1)')

    def test_old_library_and_quiz_links_lead_parents_to_the_family_page(self):
        r = self.client.get(reverse('content_view', args=[self.content.pk]))
        self.assertRedirects(r, reverse('parent_news_detail', args=[self.content.pk]))
        self.assertRedirects(self.client.get(reverse('library')), reverse('parent_news'))
        self.assertRedirects(self.client.get(reverse('quizzes')), reverse('parent_news'))

    def test_parent_takes_the_quiz_on_the_topic_page(self):
        from awarenessapp.models import Quiz, QuizChoice, QuizQuestion
        quiz = Quiz.objects.create(content=self.content, title='q', created_by=self.analyst)
        q = QuizQuestion.objects.create(quiz=quiz, question_text='Share your PIN?', order=1)
        right = QuizChoice.objects.create(question=q, choice_text='Never', is_correct=True)
        QuizChoice.objects.create(question=q, choice_text='Yes', is_correct=False)
        r = self.client.post(reverse('parent_news_detail', args=[self.content.pk]), {'action': 'quiz', f'q{q.pk}': right.pk})
        self.assertContains(r, 'You got 1 out of 1')
        self.assertEqual(QuizAttempt.objects.get(user=self.parent).score, 1)
        self.assertContains(self.client.get(reverse('parent_news')), 'Quiz done')
        self.assertRedirects(self.client.get(reverse('take_quiz', args=[quiz.pk])),
                             reverse('parent_news_detail', args=[self.content.pk]) + '#quiz', fetch_redirect_response=False)

    def test_awareness_email_links_to_the_family_page_with_family_wording(self):
        from awarenessapp.models import EmailCampaign
        from awarenessapp.services.email_service import build_email_body
        campaign = EmailCampaign.objects.create(content=self.content, subject='News', created_by=self.analyst)
        html = build_email_body(campaign)
        self.assertIn('http://testserver' + reverse('parent_news_detail', args=[self.content.pk]), html)
        self.assertNotIn('send to my children', html.lower())   # sending lives on the topic page, not in the email
        self.assertIn('<li>Show a parent.</li>', html)
        self.assertNotIn('Security Awareness', html)
        self.assertNotIn("['Do not", html)


@override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend', SITE_URL='http://testserver')
class ParentChildVersionTests(TestCase):
    """Parent asks for, sees and edits the child version; analysts control edits; campaigns publish it."""

    def setUp(self):
        cache.clear()
        self.analyst = Users.objects.create_user(email='a@x.ug', password=PASSWORD, role=ROLE_ANALYST)
        self.parent = Users.objects.create_user(email='p@x.ug', password=PASSWORD, role=ROLE_PARENT)
        self.content = AwarenessContent.objects.create(created_by=self.analyst, threat_type='reward', title='Free airtime scam',
                                                       risk='Steals PINs', action='Do not click', status='approved')
        self.child = ChildProfile.objects.create(nickname='Tutu', age_band='11-13', created_by=self.parent, email='tutu@x.ug')
        GuardianChildLink.objects.create(guardian=self.parent, child=self.child)
        self.url = reverse('parent_news_detail', args=[self.content.pk])

    def make_pack(self, publish=True):
        with fake_generate():
            pack = generate_pack(self.content, user=self.analyst)
        if publish:
            pack.status = TopicPack.STATUS_PUBLISHED
            pack.save()
        return pack

    def edit_data(self, **over):
        data = {'action': 'save_edit', 'practice_subject': 'Tutu, free data for you', 'child_title': 'Our family airtime lesson',
                'practice_body': 'Hi {name}, claim 10GB free data now at {link}', 'child_story': 'Tutu got a message.',
                'child_points': 'Too good to be true\nAsks you to hurry', 'child_action': 'Show Mum.'}
        data.update(over)
        return data

    def test_parent_asks_for_the_child_version_and_is_told_when_it_is_published(self):
        from phishsim.models import ChildVersionRequest
        from phishsim.services import versions
        self.client.login(email='p@x.ug', password=PASSWORD)
        with mock.patch('phishsim.services.autogen.start') as start:
            self.client.post(self.url, {'action': 'request_child_version'})
        start.assert_called_once()
        self.assertTrue(ChildVersionRequest.objects.filter(content=self.content, parent=self.parent).exists())
        self.assertContains(self.client.get(self.url), 'You asked for the child lesson')
        pack = self.make_pack(publish=False)
        versions.publish(pack)
        self.assertIsNotNone(ChildVersionRequest.objects.get(parent=self.parent).resolved_at)
        self.assertIn('is ready', mail.outbox[-1].subject)

    def test_parent_sees_and_edits_the_child_version_which_reaches_their_child(self):
        pack = self.make_pack()
        self.client.login(email='p@x.ug', password=PASSWORD)
        page = self.client.get(self.url)
        self.assertContains(page, 'The free airtime trick')                      # Guardian's version is shown
        self.assertContains(page, 'Edit for my children')
        r = self.client.post(self.url, self.edit_data())
        self.assertEqual(r.status_code, 302)
        self.assertContains(self.client.get(self.url), 'Your wording')
        # the child sees the parent's lesson
        kid = Users.objects.create_user(email='tutu@x.ug', password=PASSWORD, role=ROLE_CHILD)
        self.child.user = kid
        self.child.save()
        self.client.logout(); self.client.login(email='tutu@x.ug', password=PASSWORD)
        self.assertContains(self.client.get(reverse('lesson', args=[pack.pk])), 'Our family airtime lesson')
        self.assertContains(self.client.get(reverse('child_lessons')), 'Our family airtime lesson')
        # and the practice email uses the parent's subject
        from phishsim.services.sender import practice_subject, send_pack_to_children
        ConsentRecord.grant(self.parent, self.child, ConsentRecord.KIND_SIMULATION, told_child=True)
        from django.utils import timezone
        self.child.notice_sent_at = timezone.now(); self.child.save()
        d = send_pack_to_children(pack, self.parent, [self.child])[0]
        self.assertEqual(d.status, 'sent')
        self.assertEqual(mail.outbox[-1].subject, 'Tutu, free data for you')
        self.assertIn('/p/', mail.outbox[-1].body)

    def test_analyst_can_undo_a_parent_edit(self):
        from phishsim.models import ParentLessonEdit
        pack = self.make_pack()
        self.client.login(email='p@x.ug', password=PASSWORD)
        self.client.post(self.url, self.edit_data())
        edit = ParentLessonEdit.objects.get()
        self.client.logout(); self.client.login(email='a@x.ug', password=PASSWORD)
        page = self.client.get(reverse('panel_pack', args=[self.content.pk]))
        self.assertContains(page, 'Our family airtime lesson')
        self.client.post(reverse('panel_pack', args=[self.content.pk]), {'action': 'revert_edit', 'edit': edit.pk, 'note': 'Too long'})
        edit.refresh_from_db()
        self.assertFalse(edit.is_active)
        self.client.logout(); self.client.login(email='p@x.ug', password=PASSWORD)
        page = self.client.get(self.url)
        self.assertContains(page, 'An analyst changed your edit back')
        self.assertContains(page, 'The free airtime trick')

    def test_unsafe_parent_edits_are_blocked(self):
        from phishsim.models import ParentLessonEdit
        self.make_pack()
        self.client.login(email='p@x.ug', password=PASSWORD)
        r = self.client.post(self.url, self.edit_data(practice_body='Hi {name}, MTN says send your PIN to {link}'))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'real organisation')
        self.assertFalse(ParentLessonEdit.objects.exists())

    def test_sending_the_campaign_publishes_the_child_version(self):
        from awarenessapp.models import EmailCampaign
        pack = self.make_pack(publish=False)
        campaign = EmailCampaign.objects.create(content=self.content, subject='News', created_by=self.analyst, target_all_staff=True)
        self.client.login(email='a@x.ug', password=PASSWORD)
        self.client.post(reverse('panel_send_campaign', args=[campaign.pk]))
        pack.refresh_from_db()
        self.assertTrue(pack.is_published)


@override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend', SITE_URL='http://testserver')
class CampaignChildVersionTests(TestCase):
    """The analyst works on the child version inside the campaign; it goes out with the parents' email."""

    def setUp(self):
        from awarenessapp.models import EmailCampaign
        cache.clear()
        self.analyst = Users.objects.create_user(email='a@x.ug', password=PASSWORD, role=ROLE_ANALYST)
        self.parent = Users.objects.create_user(email='p@x.ug', password=PASSWORD, role=ROLE_PARENT)
        self.content = AwarenessContent.objects.create(created_by=self.analyst, threat_type='reward', title='Free airtime scam',
                                                       risk='Steals PINs', action='Do not click', status='approved')
        self.campaign = EmailCampaign.objects.create(content=self.content, subject='News', created_by=self.analyst)
        self.client.login(email='a@x.ug', password=PASSWORD)
        self.page = reverse('panel_campaign_detail', args=[self.campaign.pk])

    def test_campaign_page_shows_the_child_version_and_parent_requests(self):
        from phishsim.models import ChildVersionRequest
        ChildVersionRequest.objects.create(content=self.content, parent=self.parent)
        r = self.client.get(self.page)
        self.assertContains(r, 'Child version and practice message')
        self.assertContains(r, 'Prepare the child version now')
        self.assertContains(r, 'p@x.ug')
        with fake_generate():
            r = self.client.post(reverse('panel_pack', args=[self.content.pk]), {'action': 'generate', 'next': self.page})
        self.assertRedirects(r, self.page)
        r = self.client.get(self.page)
        self.assertContains(r, 'The free airtime trick')
        self.assertContains(r, 'Send campaign and child version')

    def test_campaign_waits_for_the_child_version(self):
        with mock.patch('phishsim.services.autogen.start') as start:
            self.client.post(reverse('panel_send_campaign', args=[self.campaign.pk]))
        start.assert_called_once()
        self.campaign.refresh_from_db()
        self.assertEqual(self.campaign.status, 'draft')
        self.client.post(reverse('panel_send_campaign', args=[self.campaign.pk]), {'without_child': '1'})
        self.campaign.refresh_from_db()
        self.assertEqual(self.campaign.status, 'sent')

    def test_safety_notes_need_a_tick_then_both_go_out(self):
        with fake_generate():
            pack = generate_pack(self.content, user=self.analyst)
        pack.safety_warnings = ['Something to check']
        pack.save()
        self.client.post(reverse('panel_send_campaign', args=[self.campaign.pk]))
        self.campaign.refresh_from_db()
        self.assertEqual(self.campaign.status, 'draft')
        self.client.post(reverse('panel_send_campaign', args=[self.campaign.pk]), {'publish_override': '1'})
        self.campaign.refresh_from_db(); pack.refresh_from_db()
        self.assertEqual(self.campaign.status, 'sent')
        self.assertTrue(pack.is_published)

    def test_generator_drops_give_away_sentences_and_unquoted_flags(self):
        from phishsim.services.generate import _normalise
        data = {**GOOD, 'practice': {**GOOD['practice'],
                'body': "Hi {name}, you won 10GB! Don't click on the link. It's not real. Tap https://x.example now.",
                'red_flags': [{'label': 'Prize', 'excerpt': 'you won 10GB'}, {'label': 'Fake', 'excerpt': 'words not there'}]}}
        out = _normalise(data)['practice']
        self.assertNotIn('not real', out['body'])
        self.assertEqual(out['body'].count('{link}'), 1)
        self.assertEqual([f['excerpt'] for f in out['red_flags']], ['you won 10GB', ''])


class AnalystSaveTests(TestCase):
    def test_saving_long_or_crlf_text_never_crashes_and_keeps_the_link(self):
        cache.clear()
        analyst = Users.objects.create_user(email='a@x.ug', password=PASSWORD, role=ROLE_ANALYST)
        content = AwarenessContent.objects.create(created_by=analyst, threat_type='reward', title='T', risk='r',
                                                  action='a', status='approved')
        with fake_generate():
            pack = generate_pack(content, user=analyst)
        self.client.login(email='a@x.ug', password=PASSWORD)
        sms = ('Free data for you!\r\n' * 30) + 'Tap {link}'
        r = self.client.post(reverse('panel_pack', args=[content.pk]), {
            'action': 'save', 'practice_sms': sms, 'practice_subject': 'S' * 300, 'child_story': 'Line one\r\nLine two'})
        self.assertEqual(r.status_code, 302)
        pack.refresh_from_db()
        self.assertLessEqual(len(pack.practice_sms), 320)
        self.assertTrue(pack.practice_sms.endswith('{link}'))
        self.assertEqual(len(pack.practice_subject), 160)
        self.assertNotIn('\r', pack.child_story)


@override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend', SITE_URL='http://testserver')
class WelcomeNoteFromTopicPageTests(TestCase):
    @override_settings(GUARDIAN_PRACTICE_OPEN=False)
    def test_parent_sends_the_missing_welcome_note_then_the_practice(self):
        cache.clear()
        analyst = Users.objects.create_user(email='a@x.ug', password=PASSWORD, role=ROLE_ANALYST)
        parent = Users.objects.create_user(email='p@x.ug', password=PASSWORD, role=ROLE_PARENT)
        content = AwarenessContent.objects.create(created_by=analyst, threat_type='reward', title='T', risk='r',
                                                  action='a', status='approved')
        with fake_generate():
            pack = generate_pack(content, user=analyst)
        pack.status = TopicPack.STATUS_PUBLISHED
        pack.save()
        child = ChildProfile.objects.create(nickname='Tutu', age_band='11-13', created_by=parent, email='tutu@x.ug')
        GuardianChildLink.objects.create(guardian=parent, child=child)
        ConsentRecord.grant(parent, child, ConsentRecord.KIND_SIMULATION, told_child=True)   # consent, but no note yet
        self.client.login(email='p@x.ug', password=PASSWORD)
        url = reverse('parent_news_detail', args=[content.pk])
        self.assertContains(self.client.get(url), 'Send welcome note now')
        self.client.post(url, {'action': 'send_notice', 'child': child.pk})
        child.refresh_from_db()
        self.assertIsNotNone(child.notice_sent_at)
        self.assertEqual(mail.outbox[-1].subject, 'Your family set up Guardian for you')
        self.client.post(url, {'action': 'send', 'children': [child.pk]})
        self.assertEqual(PracticeDelivery.objects.get(child=child).status, 'sent')


@override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend', SITE_URL='http://testserver',
                   GUARDIAN_PRACTICE_OPEN=True)
class OpenPracticeDemoTests(TestCase):
    """Demo mode: any child with an email can be sent the practice message, with the welcome note, and re-sent."""

    def test_new_child_gets_welcome_note_and_practice_together_and_can_be_resent(self):
        cache.clear()
        analyst = Users.objects.create_user(email='a@x.ug', password=PASSWORD, role=ROLE_ANALYST)
        parent = Users.objects.create_user(email='p@x.ug', password=PASSWORD, role=ROLE_PARENT)
        content = AwarenessContent.objects.create(created_by=analyst, threat_type='reward', title='T', risk='r',
                                                  action='a', status='approved')
        with fake_generate():
            pack = generate_pack(content, user=analyst)
        pack.status = TopicPack.STATUS_PUBLISHED
        pack.save()
        child = ChildProfile.objects.create(nickname='Marvin', age_band='11-13', created_by=parent, email='marvin@x.ug')
        GuardianChildLink.objects.create(guardian=parent, child=child)          # no consent, no welcome note yet
        no_email = ChildProfile.objects.create(nickname='NoMail', age_band='8-10', created_by=parent)
        GuardianChildLink.objects.create(guardian=parent, child=no_email)
        self.client.login(email='p@x.ug', password=PASSWORD)
        url = reverse('parent_news_detail', args=[content.pk])
        page = self.client.get(url).content.decode()
        self.assertIn(f'value="{child.pk}" class="mt-1" checked', page)          # selectable straight away
        self.assertIn('No email address yet', page)                              # children without email still cannot be sent
        self.client.post(url, {'action': 'send', 'children': [child.pk]})
        subjects = [m.subject for m in mail.outbox]
        self.assertIn('Your family set up Guardian for you', subjects)           # welcome note first
        self.assertEqual(len(mail.outbox), 2)                                    # then the practice email
        self.client.post(url, {'action': 'send', 'children': [child.pk]})        # resend for the demo
        self.assertEqual(len(mail.outbox), 3)                                    # practice again, no second welcome note
        self.assertContains(self.client.get(url), 'tick to send again')
