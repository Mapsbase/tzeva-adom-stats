import logging
from collections import Counter
from datetime import timedelta
from datetime import timezone as dt_timezone

from django.conf import settings
from django.db.models import Count
from django.shortcuts import render
from django.utils.decorators import method_decorator
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.csrf import ensure_csrf_cookie
from rest_framework.response import Response
from rest_framework.views import APIView

from .fetchers import (
    category_labels,
    city_labels,
    district_labels_from_name,
    fetch_history_events,
    fetch_live_events_with_status,
    history_city_metadata,
    source_labels,
)
from .models import Alert
from .serializers import AlertSerializer
from .services import ingest_alerts


ACTIONABLE_CATEGORIES = ["rocket_missile", "hostile_aircraft"]
logger = logging.getLogger(__name__)
ARCHIVE_DEFAULT_START = timezone.datetime(2022, 1, 1, tzinfo=dt_timezone.utc)


def parse_iso_datetime(value):
    parsed = timezone.datetime.fromisoformat(value.replace("Z", "+00:00"))
    if timezone.is_naive(parsed):
        parsed = parsed.replace(tzinfo=dt_timezone.utc)
    return parsed


@ensure_csrf_cookie
def dashboard(request):
    return render(request, "alerts/dashboard.html", {"live_poll_seconds": settings.LIVE_POLL_SECONDS})


def map_lab(request):
    return render(request, "alerts/map_lab.html")


def build_event_key(row: dict):
    raw = row.get("raw_payload") or {}
    alert_id = raw.get("alert_id")
    cities = raw.get("cities") or []
    timestamp = raw.get("timestamp") or row["occurred_at"].isoformat()
    threat = raw.get("threat", row["category"])

    if alert_id is not None:
        return ("alert_id", str(alert_id), str(threat), str(timestamp), tuple(cities))

    normalized_cities = tuple(sorted(cities)) if isinstance(cities, list) else (str(cities),)
    return ("fallback", row["occurred_at"].isoformat(), row["category"], normalized_cities)


def calculate_event_stats(*, start, end) -> dict:
    queryset = Alert.objects.filter(occurred_at__gte=start, occurred_at__lte=end).order_by("occurred_at", "id")
    rows = list(queryset.values("occurred_at", "category", "city", "district", "raw_payload"))
    metadata = history_city_metadata()

    events = {}
    city_to_district = {}
    for row in rows:
        key = build_event_key(row)
        event = events.setdefault(
            key,
            {
                "occurred_at": row["occurred_at"],
                "category": row["category"],
                "districts": set(),
                "cities": set(),
                "sources": set(),
            },
        )
        if row["district"]:
            event["districts"].add(row["district"])
            if row["city"] and row["city"] not in city_to_district:
                city_to_district[row["city"]] = row["district"]
        event["cities"].add(row["city"])
        provider = (row["raw_payload"] or {}).get("provider") or (row["raw_payload"] or {}).get("source")
        if provider:
            event["sources"].add(provider)

    city_counter = Counter()
    district_counter = Counter()
    hour_counter = Counter()
    minute_counter = Counter()
    category_counter = Counter()
    day_counter = Counter()
    source_counter = Counter()
    map_points = {}

    for event in events.values():
        category_counter[event["category"]] += 1
        hour_counter[event["occurred_at"].hour] += 1
        minute_counter[event["occurred_at"].minute] += 1
        day_counter[event["occurred_at"].date().isoformat()] += 1
        for source in event["sources"]:
            source_counter[source] += 1
        for city in event["cities"]:
            city_counter[city] += 1
            city_info = (metadata.get("cities") or {}).get(city, {})
            if city not in map_points and city_info.get("lat") is not None and city_info.get("lng") is not None:
                map_points[city] = {
                    "city": city,
                    "city_label": city_labels(city).get("he") or city,
                    "city_labels": city_labels(city),
                    "district": city_to_district.get(city, ""),
                    "district_labels": district_labels_from_name(city_to_district.get(city, "")),
                    "lat": city_info.get("lat"),
                    "lng": city_info.get("lng"),
                }
        for district in event["districts"]:
            district_counter[district] += 1

    top_cities = [
        {
            "rank": index,
            "city": city,
            "city_label": city_labels(city).get("he") or city,
            "city_labels": city_labels(city),
            "count": count,
        }
        for index, (city, count) in enumerate(city_counter.most_common(), start=1)
    ]
    top_districts = [
        {
            "rank": index,
            "district": district,
            "district_label": district_labels_from_name(district).get("he") or district,
            "district_labels": district_labels_from_name(district),
            "count": count,
        }
        for index, (district, count) in enumerate(district_counter.most_common(), start=1)
    ]
    top_map_points = []
    for row in top_cities:
        point = map_points.get(row["city"])
        if point:
            top_map_points.append({**point, "count": row["count"], "rank": row["rank"]})

    return {
        "total_city_rows": len(rows),
        "total_event_count": len(events),
        "top_cities": top_cities,
        "top_districts": top_districts,
        "by_hour": [{"hour": hour, "count": hour_counter.get(hour, 0)} for hour in range(24)],
        "by_minute": [{"minute": minute, "count": minute_counter.get(minute, 0)} for minute in range(60)],
        "by_day": [{"day": day, "count": count} for day, count in sorted(day_counter.items())],
        "by_category": [
            {
                "category": category,
                "category_label": category_labels(category).get("he") or category,
                "category_labels": category_labels(category),
                "count": count,
            }
            for category, count in category_counter.most_common()
        ],
        "by_source": [
            {
                "source": source,
                "source_label": source_labels(source).get("he") or source,
                "source_labels": source_labels(source),
                "count": count,
            }
            for source, count in source_counter.most_common()
        ],
        "map_points": top_map_points,
    }


class LatestAlertsView(APIView):
    def get(self, request):
        limit = min(int(request.GET.get("limit", 50)), 500)
        queryset = Alert.objects.order_by("-occurred_at", "-id")[:limit]
        return Response(
            {
                "count": len(queryset),
                "alerts": AlertSerializer(queryset, many=True).data,
            }
        )


class LiveFeedView(APIView):
    def get(self, request):
        limit = min(int(request.GET.get("limit", 50)), 200)
        since_id = request.GET.get("since_id")
        minutes = max(1, min(int(request.GET.get("minutes", 180)), 1440))
        include_history = request.GET.get("include_history", "0") == "1"
        refresh = request.GET.get("refresh", "1") != "0"
        created = []
        refresh_error = None
        source_status = "idle"
        source_url = None
        source_event_count = 0

        if refresh:
            try:
                result = fetch_live_events_with_status()
                created = ingest_alerts(result.events)
                source_status = result.source_status
                source_url = result.source_url
                source_event_count = result.source_event_count
                source_details = result.source_details or []
                if result.source_error:
                    refresh_error = result.source_error
            except Exception as exc:
                logger.exception("Realtime refresh failed")
                refresh_error = str(exc)
                source_status = "error"
                source_details = []
        else:
            source_details = []

        queryset = Alert.objects.order_by("-occurred_at", "-id")
        if not include_history:
            queryset = queryset.filter(source__in=["oref_realtime", "live_consensus"])
        cutoff = timezone.now() - timedelta(minutes=minutes)
        queryset = queryset.filter(occurred_at__gte=cutoff)
        if since_id:
            try:
                queryset = queryset.filter(id__gt=int(since_id))
            except ValueError:
                queryset = queryset.none()
        alerts = list(queryset[:limit])

        return Response(
            {
                "refreshed": refresh,
                "new_count": len(created),
                "newest_id": Alert.objects.order_by("-id").values_list("id", flat=True).first(),
                "server_time": timezone.now().isoformat(),
                "refresh_error": refresh_error,
                "source_status": source_status,
                "source_url": source_url,
                "source_event_count": source_event_count,
                "source_details": source_details,
                "include_history": include_history,
                "minutes": minutes,
                "alerts": AlertSerializer(alerts, many=True).data,
            }
        )


class PullRealtimeView(APIView):
    @method_decorator(csrf_exempt)
    def post(self, request):
        try:
            result = fetch_live_events_with_status()
            created = ingest_alerts(result.events)
            status_code = 200 if result.source_status in {"ok", "empty"} else 502
            return Response(
                {
                    "created": len(created),
                    "server_time": timezone.now().isoformat(),
                    "refresh_error": result.source_error,
                    "source_status": result.source_status,
                    "source_url": result.source_url,
                    "source_event_count": result.source_event_count,
                    "source_details": result.source_details or [],
                },
                status=status_code,
            )
        except Exception as exc:
            logger.exception("Manual realtime pull failed")
            return Response(
                {
                    "created": 0,
                    "server_time": timezone.now().isoformat(),
                    "refresh_error": str(exc),
                    "source_status": "error",
                    "source_url": None,
                    "source_event_count": 0,
                    "source_details": [],
                },
                status=502,
            )


class PullHistoryView(APIView):
    @method_decorator(csrf_exempt)
    def post(self, request):
        start_text = request.data.get("start")
        if start_text:
            start = parse_iso_datetime(start_text)
        else:
            start = ARCHIVE_DEFAULT_START
        end = timezone.now()
        created = ingest_alerts(fetch_history_events(start=start, end=end))
        return Response({"created": len(created), "start": start.isoformat(), "end": end.isoformat()})


class TopCitiesView(APIView):
    def get(self, request):
        start_text = request.GET.get("start")
        end_text = request.GET.get("end")
        db_start = Alert.objects.order_by("occurred_at").values_list("occurred_at", flat=True).first()
        db_end = Alert.objects.order_by("-occurred_at").values_list("occurred_at", flat=True).first()

        if start_text:
            start = parse_iso_datetime(start_text)
        else:
            start = db_start or ARCHIVE_DEFAULT_START
        if end_text:
            end = parse_iso_datetime(end_text)
        else:
            end = db_end or timezone.now()

        limit = min(int(request.GET.get("limit", 500)), 5000)
        queryset = Alert.objects.filter(
            occurred_at__gte=start,
            occurred_at__lte=end,
            category__in=ACTIONABLE_CATEGORIES,
        )
        distinct_city_count = queryset.values("city").distinct().count()
        actionable_alert_count = queryset.count()
        rows = list(
            queryset.values("city")
            .annotate(count=Count("id"))
            .order_by("-count", "city")[:limit]
        )
        for index, row in enumerate(rows, start=1):
            row["rank"] = index
            row["city_label"] = city_labels(row["city"]).get("he") or row["city"]
            row["city_labels"] = city_labels(row["city"])
        return Response(
            {
                "start": start.isoformat(),
                "end": end.isoformat(),
                "db_start": db_start.isoformat() if db_start else None,
                "db_end": db_end.isoformat() if db_end else None,
                "distinct_city_count": distinct_city_count,
                "actionable_alert_count": actionable_alert_count,
                "returned_count": len(rows),
                "results": rows,
            }
        )


class RangeOverviewView(APIView):
    def get(self, request):
        start_text = request.GET.get("start")
        end_text = request.GET.get("end")
        db_start = Alert.objects.order_by("occurred_at").values_list("occurred_at", flat=True).first()
        db_end = Alert.objects.order_by("-occurred_at").values_list("occurred_at", flat=True).first()

        if start_text:
            start = parse_iso_datetime(start_text)
        else:
            start = db_start or ARCHIVE_DEFAULT_START

        if end_text:
            requested_end = parse_iso_datetime(end_text)
        else:
            requested_end = db_end or timezone.now()

        if not db_end:
            return Response(
                {
                    "start": start.isoformat(),
                    "requested_end": requested_end.isoformat(),
                    "effective_end": None,
                    "db_start": None,
                    "db_end": None,
                    "total_city_rows": 0,
                    "total_event_count": 0,
                    "top_cities": [],
                    "top_districts": [],
                    "by_hour": [{"hour": hour, "count": 0} for hour in range(24)],
                    "by_minute": [{"minute": minute, "count": 0} for minute in range(60)],
                    "by_day": [],
                    "by_category": [],
                    "by_source": [],
                    "map_points": [],
                }
            )

        effective_end = min(requested_end, db_end)
        stats = calculate_event_stats(start=start, end=effective_end)

        return Response(
            {
                "start": start.isoformat(),
                "requested_end": requested_end.isoformat(),
                "effective_end": effective_end.isoformat(),
                "db_start": db_start.isoformat() if db_start else None,
                "db_end": db_end.isoformat() if db_end else None,
                **stats,
            }
        )
