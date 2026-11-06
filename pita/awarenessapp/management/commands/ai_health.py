"""Check Django can reach guardian-ai and run one synthetic classification (plan.md §6.8)."""
import json

from django.conf import settings
from django.core.management.base import BaseCommand

from awarenessapp.services import ai_client

SYNTHETIC_SCAM = 'Congratulations! You won UGX 500,000 in the youth draw. Send your Mobile Money PIN to claim today.'


class Command(BaseCommand):
    help = 'Show guardian-ai /health and run one synthetic /classify call.'

    def handle(self, *args, **options):
        self.stdout.write(f'GUARDIAN_AI_URL = {settings.GUARDIAN_AI_URL}')

        h = ai_client.health()
        if h.get('status') not in ('ready', 'degraded'):
            self.stderr.write(self.style.ERROR(f"Unreachable: {h.get('meta', {}).get('error')}"))
            raise SystemExit(1)
        self.stdout.write(f"Service {h['status']} · mode {h['mode']} · host {h['host']} · GPU {h['gpu']}")
        for capability, rows in h['backends'].items():
            parts = [f"{r['name']}: {'ready' if r['ready'] else r.get('reason', 'not ready')}" for r in rows]
            self.stdout.write(f'  {capability:9s} {" | ".join(parts)}')

        c = ai_client.classify(SYNTHETIC_SCAM)
        meta = c.get('meta', {})
        if c.get('status') != 'ok':
            self.stderr.write(self.style.WARNING(
                f"classify unavailable · attempts {json.dumps(meta.get('attempts', meta.get('error')))}"))
            raise SystemExit(2)
        self.stdout.write(self.style.SUCCESS(
            f"classify ok · score {c['spamScore']} ({c['scoreKind']}) · backend {meta['backend']} "
            f"({meta['model']}) · mode {meta['mode']} · {meta['latencyMs']} ms"))

        u = ai_client.classify_urls(['http://mtn-ug-rewards.example/claim.php?id=88', 'https://www.mtn.co.ug/'])
        if u.get('status') == 'ok':
            scores = ', '.join(f"{r['phishingScore']} {r['url']}" for r in u['results'])
            self.stdout.write(self.style.SUCCESS(f"classify-url ok · {scores} · backend {u['meta']['backend']}"))
        else:
            self.stderr.write(self.style.WARNING(f"classify-url unavailable · {u.get('meta', {}).get('attempts')}"))
