import time

from django.conf import settings
from django.core.management.base import BaseCommand

from alerts.fetchers import fetch_live_events_with_status
from alerts.services import ingest_alerts


class Command(BaseCommand):
    help = "Run a simple forever loop that fetches realtime alerts"

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS(f"Polling every {settings.LIVE_POLL_SECONDS} seconds"))
        while True:
            try:
                result = fetch_live_events_with_status()
                created = ingest_alerts(result.events)
                self.stdout.write(
                    f"status={result.source_status} created={len(created)} source_events={result.source_event_count} source={result.source_url or '-'}"
                )
                if result.source_error:
                    self.stdout.write(self.style.WARNING(f"source_error={result.source_error}"))
            except Exception as exc:  # noqa: BLE001
                self.stdout.write(self.style.ERROR(f"poll_error={exc}"))
            time.sleep(settings.LIVE_POLL_SECONDS)
