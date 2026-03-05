from datetime import timezone as dt_timezone

from django.core.management.base import BaseCommand
from django.utils import timezone

from alerts.fetchers import fetch_history_events
from alerts.models import Alert
from alerts.services import ingest_alerts


class Command(BaseCommand):
    help = "Bootstrap history data if alerts table is empty"

    def add_arguments(self, parser):
        parser.add_argument("--start", type=str)

    def handle(self, *args, **options):
        if Alert.objects.exists():
            self.stdout.write(self.style.SUCCESS("bootstrap_data: alerts table already has data, skipping"))
            return

        if options.get("start"):
            start = timezone.datetime.fromisoformat(options["start"].replace("Z", "+00:00"))
            if timezone.is_naive(start):
                start = start.replace(tzinfo=dt_timezone.utc)
        else:
            default_start = "2026-02-27T00:00:00Z"
            start = timezone.datetime.fromisoformat(default_start.replace("Z", "+00:00"))

        end = timezone.now()
        self.stdout.write(f"bootstrap_data: ingesting history start={start.isoformat()} end={end.isoformat()}")
        created = ingest_alerts(fetch_history_events(start=start, end=end))
        self.stdout.write(self.style.SUCCESS(f"bootstrap_data: created={len(created)}"))

