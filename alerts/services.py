from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone as dt_timezone
from typing import Iterable

from django.db import transaction
from django.utils import timezone

from .models import Alert


def _as_utc_datetime(value) -> datetime:
    if isinstance(value, datetime):
        parsed = value
    else:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if timezone.is_naive(parsed):
        parsed = parsed.replace(tzinfo=dt_timezone.utc)
    return parsed.astimezone(dt_timezone.utc)


def _normalize_event(event: dict) -> dict | None:
    try:
        source = str(event.get("source") or "").strip()
        category = str(event.get("category") or "").strip()
        city = str(event.get("city") or "").strip()
        if not source or not category or not city:
            return None
        return {
            "source": source,
            "occurred_at": _as_utc_datetime(event.get("occurred_at")),
            "category": category,
            "city": city,
            "district": str(event.get("district") or "").strip(),
            "raw_payload": event.get("raw_payload") or {},
        }
    except Exception:  # noqa: BLE001
        return None


def ingest_alerts(events: Iterable[dict]) -> list[Alert]:
    unique = {}
    for event in events:
        normalized = _normalize_event(event)
        if not normalized:
            continue
        key = (
            normalized["source"],
            normalized["occurred_at"],
            normalized["category"],
            normalized["city"],
        )
        unique[key] = normalized

    if not unique:
        return []

    rows = [Alert(**payload) for payload in unique.values()]

    with transaction.atomic():
        Alert.objects.bulk_create(rows, ignore_conflicts=True, batch_size=1000)

    # Resolve created-or-existing rows in grouped batches instead of one query per row.
    grouped = defaultdict(list)
    for source, occurred_at, category, city in unique.keys():
        grouped[source].append((occurred_at, category, city))

    resolved = []
    for source, keys in grouped.items():
        occurred_values = [item[0] for item in keys]
        city_values = [item[2] for item in keys]
        category_values = [item[1] for item in keys]
        queryset = Alert.objects.filter(
            source=source,
            occurred_at__in=occurred_values,
            category__in=category_values,
            city__in=city_values,
        ).order_by("-occurred_at", "-id")
        resolved.extend(list(queryset))

    # Keep only rows that match the incoming unique keys exactly.
    wanted = set(unique.keys())
    return [
        row
        for row in resolved
        if (row.source, row.occurred_at, row.category, row.city) in wanted
    ]
