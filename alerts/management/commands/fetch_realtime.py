from django.core.management.base import BaseCommand

from alerts.fetchers import fetch_live_events_with_status
from alerts.services import ingest_alerts


class Command(BaseCommand):
    help = "Fetch realtime alerts from Oref and ingest them"

    def handle(self, *args, **options):
        result = fetch_live_events_with_status()
        created = ingest_alerts(result.events)
        self.stdout.write(
            self.style.SUCCESS(
                f"status={result.source_status} created={len(created)} source_events={result.source_event_count} source={result.source_url or '-'}"
            )
        )
        if result.source_error:
            self.stdout.write(self.style.WARNING(f"source_error={result.source_error}"))
