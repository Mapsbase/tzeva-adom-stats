from datetime import timezone as dt_timezone

from django.core.management.base import BaseCommand
from django.utils import timezone

from alerts.fetchers import fetch_history_events
from alerts.services import ingest_alerts


class Command(BaseCommand):
    help = "Fetch historical alerts from tzevaadom and ingest them"

    def add_arguments(self, parser):
        parser.add_argument("--start", type=str)

    def handle(self, *args, **options):
        if options.get("start"):
            start = timezone.datetime.fromisoformat(options["start"].replace("Z", "+00:00"))
            if timezone.is_naive(start):
                start = start.replace(tzinfo=dt_timezone.utc)
        else:
            start = timezone.datetime(2022, 1, 1, tzinfo=dt_timezone.utc)
        end = timezone.now()
        created = ingest_alerts(fetch_history_events(start=start, end=end))
        self.stdout.write(self.style.SUCCESS(f"Created {len(created)} alerts"))
