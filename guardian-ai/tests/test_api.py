import json

from guardian_ai.backends.base import BackendError
from guardian_ai.config import Settings
from guardian_ai.backends.gemini import GeminiBackend

from .conftest import GOOD, make_fake, png_bytes

SCAM = 'Congratulations! You won UGX 500,000. Send your Mobile Money PIN to claim.'


def test_classify_uses_first_working_backend(client, register):
    register(a=make_fake('a', cloud=True, reply=GOOD), b=make_fake('b', reply=GOOD))
    r = client.post('/classify', json={'text': SCAM}).json()
    assert r['status'] == 'ok'
    assert r['spamScore'] == 0.91 and r['label'] == 1 and r['calibrated'] is False
    assert r['meta']['backend'] == 'a' and r['meta']['mode'] == 'cloud-dev'
    assert r['meta']['attempts'] == [{'backend': 'a', 'ok': True}]


def test_falls_back_when_first_backend_fails(client, register):
    register(a=make_fake('a', fail=BackendError('quota')), b=make_fake('b', reply=GOOD))
    r = client.post('/classify', json={'text': SCAM}).json()
    assert r['status'] == 'ok' and r['meta']['backend'] == 'b' and r['meta']['mode'] == 'live'
    assert r['meta']['attempts'][0] == {'backend': 'a', 'ok': False, 'error': 'quota'}


def test_unexpected_crash_is_contained(client, register):
    register(a=make_fake('a', fail=RuntimeError('boom')), b=make_fake('b', reply=GOOD))
    r = client.post('/classify', json={'text': SCAM}).json()
    assert r['status'] == 'ok' and r['meta']['attempts'][0]['error'] == 'unexpected RuntimeError'


def test_malformed_reply_counts_as_failure(client, register):
    register(a=make_fake('a', reply={'classify': {'label': 'scam'}}), b=make_fake('b', reply=GOOD))
    assert client.post('/classify', json={'text': SCAM}).json()['meta']['backend'] == 'b'


def test_all_backends_down_is_unavailable_not_an_error(client, register):
    register(a=make_fake('a', unavailable='not configured'), b=make_fake('b', fail=BackendError('down')))
    r = client.post('/classify', json={'text': SCAM})
    assert r.status_code == 200
    body = r.json()
    assert body['status'] == 'unavailable' and 'spamScore' not in body
    assert body['meta']['mode'] == 'unable_to_verify'


def test_score_is_clamped(client, register):
    register(a=make_fake('a', reply={'classify': {'spamScore': 7}}), b=make_fake('b'))
    assert client.post('/classify', json={'text': SCAM}).json()['spamScore'] == 1.0


def test_classify_validates_input(client, register):
    register(a=make_fake('a', reply=GOOD), b=make_fake('b'))
    assert client.post('/classify', json={'text': ''}).status_code == 422
    assert client.post('/classify', json={'text': 'x' * 5001}).status_code == 422


def test_extract_normalises_reply(client, register):
    reply = {'extract': {'messages': [{'sender_role': 'scammer', 'text': 'Pay now'}, {'text': ''}],
                         'claimed_organisation': 'null', 'language': 'fr'}}
    register(a=make_fake('a', reply=reply), b=make_fake('b'))
    r = client.post('/extract', files={'file': ('s.png', png_bytes(), 'image/png')}).json()
    assert r['status'] == 'ok'
    assert r['messages'] == [{'sender_role': 'unclear', 'text': 'Pay now'}]
    assert r['claimed_organisation'] is None and r['language'] == 'other'


def test_extract_rejects_non_images_and_large_files(client, register, settings):
    register(a=make_fake('a', reply=GOOD), b=make_fake('b'))
    r = client.post('/extract', files={'file': ('x.png', b'MZ\x90\x00 not an image', 'image/png')})
    assert r.status_code == 415
    big = b'\x89PNG\r\n\x1a\n' + b'0' * settings.max_image_bytes
    assert client.post('/extract', files={'file': ('b.png', big, 'image/png')}).status_code == 413


def test_extract_reencodes_and_downscales(client, register, settings):
    fake = make_fake('a', reply=GOOD)
    register(a=fake, b=make_fake('b'))
    client.post('/extract', files={'file': ('s.png', png_bytes((4000, 1000)), 'image/png')})
    from PIL import Image
    import io
    _, (image, mime) = fake.calls[-1]
    w, h = Image.open(io.BytesIO(image)).size
    assert mime == 'image/png' and max(w, h) == settings.max_image_side


def test_explain_rejects_false_certainty(client, register):
    bad = {'explain': {'explanation': 'This is 100% safe.', 'recommendedActions': []}}
    register(a=make_fake('a', reply=bad), b=make_fake('b', reply=GOOD))
    r = client.post('/explain', json={'riskLevel': 'low', 'signals': [], 'audience': 'child'}).json()
    assert r['meta']['backend'] == 'b' and '100%' not in r['explanation']


def test_explain_validates_risk_level(client, register):
    register(a=make_fake('a', reply=GOOD), b=make_fake('b'))
    assert client.post('/explain', json={'riskLevel': 'safe'}).status_code == 422


def test_token_required_when_configured(client, register, settings):
    register(a=make_fake('a', reply=GOOD), b=make_fake('b'))
    settings.guardian_ai_token = 's3cret'
    assert client.post('/classify', json={'text': SCAM}).status_code == 401
    ok = client.post('/classify', json={'text': SCAM}, headers={'X-Guardian-AI-Key': 's3cret'})
    assert ok.status_code == 200
    assert client.get('/health').status_code == 200          # health stays open


def test_health_reports_readiness_and_mode(client, register):
    register(a=make_fake('a', cloud=True, unavailable='GEMINI_API_KEY is not set'), b=make_fake('b'))
    h = client.get('/health').json()
    assert h['status'] == 'ready' and h['mode'] == 'live'
    assert h['backends']['classify'][0] == {'name': 'a', 'ready': False, 'cloud': True,
                                            'reason': 'GEMINI_API_KEY is not set'}


def test_health_degraded_when_a_capability_has_no_backend(client, register):
    register(a=make_fake('a', unavailable='x'), b=make_fake('b', unavailable='y'))
    assert client.get('/health').json()['status'] == 'degraded'


def test_inference_log_has_no_content(client, register, settings):
    register(a=make_fake('a', reply=GOOD), b=make_fake('b'))
    client.post('/classify', json={'text': SCAM})
    line = json.loads(open(settings.inference_log).read().splitlines()[-1])
    assert line['endpoint'] == 'classify' and line['backend'] == 'a' and len(line['inputSha256']) == 64
    assert 'PIN' not in json.dumps(line)


def test_gemini_respects_cloud_switches():
    s = Settings(_env_file=None, gemini_api_key='k', allow_cloud_images=False)
    g = GeminiBackend(s)
    g.check('classify')
    for cap, settings in (('extract', s), ('classify', Settings(_env_file=None, gemini_api_key='k', allow_cloud=False)),
                          ('classify', Settings(_env_file=None, gemini_api_key=''))):
        try:
            GeminiBackend(settings).check(cap)
        except BackendError:
            continue
        raise AssertionError(f'{cap} should be unavailable')


def test_health_mode_when_nothing_is_ready(client, register):
    register(a=make_fake('a', cloud=True, unavailable='x'), b=make_fake('b', unavailable='y'))
    assert client.get('/health').json()['mode'] == 'unable_to_verify'


def test_classify_url_scores_each_url_in_order(client, register):
    register(a=make_fake('a'), b=make_fake('b'))
    r = client.post('/classify-url', json={'urls': ['http://mtn-bonus.example/win', 'https://mtn.co.ug']}).json()
    assert r['status'] == 'ok' and r['scoreKind'] == 'uncalibrated-model-score'
    assert [(x['url'], x['label']) for x in r['results']] == [('http://mtn-bonus.example/win', 1), ('https://mtn.co.ug', 0)]


def test_classify_url_validates(client, register):
    register(a=make_fake('a'), b=make_fake('b'))
    assert client.post('/classify-url', json={'urls': []}).status_code == 422
    assert client.post('/classify-url', json={'urls': ['u'] * 21}).status_code == 422


def test_embed_returns_one_vector_per_text(client, register):
    register(a=make_fake('a'), b=make_fake('b'))
    r = client.post('/embed', json={'texts': ['one', 'two']}).json()
    assert r['status'] == 'ok' and len(r['vectors']) == 2 and r['dimensions'] == 3


def test_generate_text_and_json(client, register):
    register(a=make_fake('a', reply=GOOD), b=make_fake('b'))
    r = client.post('/generate', json={'prompt': 'Write a lesson', 'json': True, 'maxTokens': 400}).json()
    assert r['status'] == 'ok' and r['data']['title'] == 'Free airtime is a trick'


def test_generate_invalid_json_falls_back(client, register):
    register(a=make_fake('a', reply={'generate': 'not json at all'}), b=make_fake('b', reply=GOOD))
    r = client.post('/generate', json={'prompt': 'Write a lesson', 'json': True}).json()
    assert r['meta']['backend'] == 'b'


def test_generate_caps_tokens(client, register, settings):
    fake = make_fake('a', reply=GOOD)
    register(a=fake, b=make_fake('b'))
    client.post('/generate', json={'prompt': 'x', 'maxTokens': 4000})
    assert fake.calls[-1][1][2] == settings.max_generate_tokens


def test_parse_json_tolerates_surrounding_text():
    from guardian_ai.backends.base import parse_json
    assert parse_json('Here you go:\n```json\n{"a": 1}\n```') == {'a': 1}
    assert parse_json('Sure! {"a": 2} Hope this helps.') == {'a': 2}


def test_explain_rejects_reassurance(client, register):
    bad = {'explain': {'explanation': 'This is a safe place to talk. You can trust it.', 'recommendedActions': []}}
    register(a=make_fake('a', reply=bad), b=make_fake('b', reply=GOOD))
    r = client.post('/explain', json={'riskLevel': 'low', 'signals': [], 'audience': 'child'}).json()
    assert r['meta']['backend'] == 'b'


def test_explain_allows_not_safe(client, register):
    ok = {'explain': {'explanation': 'This is not safe. Do not share your PIN.', 'recommendedActions': []}}
    register(a=make_fake('a', reply=ok), b=make_fake('b'))
    assert client.post('/explain', json={'riskLevel': 'high', 'signals': []}).json()['meta']['backend'] == 'a'



def test_extract_bubble_side_decides_sender_role(client, register):
    reply = {'extract': {'messages': [{'side': 'right', 'sender_role': 'other', 'text': 'Which code?'},
                                      {'side': 'left', 'sender_role': 'child', 'text': 'Send it back'},
                                      {'side': 'none', 'sender_role': 'other', 'text': 'Dear customer'}]}}
    register(a=make_fake('a', reply=reply), b=make_fake('b'))
    r = client.post('/extract', files={'file': ('s.png', png_bytes(), 'image/png')}).json()
    assert [m['sender_role'] for m in r['messages']] == ['child', 'other', 'other']
