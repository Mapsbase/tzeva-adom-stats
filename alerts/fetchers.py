from __future__ import annotations

import json
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone as dt_timezone
from functools import lru_cache
from zoneinfo import ZoneInfo

import requests
from django.conf import settings


THREAT_CATEGORY_MAP = {
    0: "rocket_missile",
    5: "hostile_aircraft",
}

CATEGORY_LABELS = {
    "rocket_missile": {
        "he": "Rocket and Missile Fire",
        "en": "Rocket and Missile Fire",
        "ru": "Rocket and Missile Fire",
    },
    "hostile_aircraft": {
        "he": "Hostile Aircraft Intrusion",
        "en": "Hostile Aircraft Intrusion",
        "ru": "Hostile Aircraft Intrusion",
    },
}

SOURCE_LABELS = {
    "tzevaadom_history": {
        "he": "TzevaAdom Archive",
        "en": "TzevaAdom Archive",
        "ru": "TzevaAdom Archive",
    },
    "oref_realtime": {
        "he": "Oref Realtime",
        "en": "Oref Realtime",
        "ru": "Oref Realtime",
    },
    "backup_notifications": {
        "he": "Backup Notifications",
        "en": "Backup Notifications",
        "ru": "Backup Notifications",
    },
    "backup_history_live": {
        "he": "Backup Live History",
        "en": "Backup Live History",
        "ru": "Backup Live History",
    },
    "live_consensus": {
        "he": "Live Source Consensus",
        "en": "Live Source Consensus",
        "ru": "Live Source Consensus",
    },
}


class UpstreamPayloadError(Exception):
    pass


@dataclass
class LiveFetchResult:
    events: list[dict]
    source_status: str
    source_url: str | None
    source_event_count: int
    source_error: str | None = None
    source_details: list[dict] | None = None


@dataclass
class ProviderFetchResult:
    provider: str
    url: str | None
    status: str
    events: list[dict]
    error: str | None = None
    raw_event_count: int = 0


def _parse_source_datetime(value) -> datetime:
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, (int, float)):
        parsed = datetime.fromtimestamp(value, tz=dt_timezone.utc)
    else:
        text = str(value).strip()
        if not text:
            raise ValueError("empty datetime value")
        parsed = (
            datetime.fromisoformat(text.replace("Z", "+00:00"))
            if "T" in text
            else datetime.strptime(text, "%Y-%m-%d %H:%M:%S")
        )

    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=ZoneInfo(settings.SOURCE_TIMEZONE))
    return parsed.astimezone(dt_timezone.utc)


def _normalize_label_bundle(he=None, en=None, ru=None, fallback="") -> dict:
    he_value = he or fallback
    en_value = en or he_value or fallback
    ru_value = ru or en_value or he_value or fallback
    return {
        "he": he_value or "",
        "en": en_value or "",
        "ru": ru_value or "",
    }


def _http_get_text(url: str, *, headers: dict, timeout: int, attempts: int = 3) -> str:
    last_error = None
    with requests.Session() as session:
        for attempt in range(1, attempts + 1):
            try:
                response = session.get(url, headers=headers, timeout=timeout)
                response.raise_for_status()
                return response.content.decode("utf-8-sig", errors="replace").strip()
            except Exception as exc:  # noqa: BLE001
                last_error = exc
                if attempt < attempts:
                    time.sleep(0.25 * attempt)
    raise last_error  # type: ignore[misc]


def _extract_json_from_text(text: str):
    if not text:
        return None

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    for marker in ("{", "["):
        index = text.find(marker)
        if index == -1:
            continue
        fragment = _extract_balanced_json_fragment(text, index)
        if not fragment:
            continue
        try:
            return json.loads(fragment)
        except json.JSONDecodeError:
            continue

    preview = text[:200].replace("\n", "\\n").replace("\r", "\\r")
    raise UpstreamPayloadError(f"Upstream returned non-JSON payload: {preview}")


def _extract_balanced_json_fragment(text: str, start_index: int) -> str | None:
    if start_index < 0 or start_index >= len(text):
        return None

    opening = text[start_index]
    if opening == "{":
        closing = "}"
    elif opening == "[":
        closing = "]"
    else:
        return None

    depth = 0
    in_string = False
    escaped = False
    for idx in range(start_index, len(text)):
        ch = text[idx]
        if in_string:
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == '"':
                in_string = False
            continue

        if ch == '"':
            in_string = True
            continue

        if ch == opening:
            depth += 1
        elif ch == closing:
            depth -= 1
            if depth == 0:
                return text[start_index:idx + 1]
    return None


def _get_json(url: str, *, headers: dict | None = None):
    request_headers = headers or {}
    timeout = int(getattr(settings, "REALTIME_TIMEOUT_SECONDS", 20))
    attempts = int(getattr(settings, "REALTIME_MAX_RETRIES", 3))
    text = _http_get_text(url, headers=request_headers, timeout=timeout, attempts=attempts)
    return _extract_json_from_text(text)


@lru_cache(maxsize=1)
def history_city_metadata() -> dict:
    if not settings.HISTORY_CITIES_URL:
        return {}
    return _get_json(settings.HISTORY_CITIES_URL) or {}


@lru_cache(maxsize=1)
def district_label_index() -> dict:
    metadata = history_city_metadata()
    mapping = {}
    for area_id, area in (metadata.get("areas") or {}).items():
        labels = _normalize_label_bundle(
            he=area.get("he"),
            en=area.get("en"),
            ru=area.get("ru"),
            fallback=str(area_id),
        )
        for key in {labels["he"], labels["en"], labels["ru"], str(area_id)}:
            if key:
                mapping[key] = labels
    return mapping


def city_labels(city: str) -> dict:
    metadata = history_city_metadata()
    city_info = (metadata.get("cities") or {}).get(city, {})
    return _normalize_label_bundle(
        he=city_info.get("he"),
        en=city_info.get("en"),
        ru=city_info.get("ru"),
        fallback=city,
    )


def district_labels_from_name(name: str) -> dict:
    labels = district_label_index().get(name)
    if labels:
        return labels
    return _normalize_label_bundle(fallback=name)


def category_labels(category: str) -> dict:
    labels = CATEGORY_LABELS.get(category)
    if labels:
        return labels
    fallback = str(category).replace("_", " ").title()
    return _normalize_label_bundle(fallback=fallback)


def source_labels(source: str) -> dict:
    labels = SOURCE_LABELS.get(source)
    if labels:
        return labels
    fallback = str(source).replace("_", " ").title()
    return _normalize_label_bundle(fallback=fallback)


def _split_city_text(value) -> list[str]:
    if isinstance(value, list):
        values = value
    else:
        text = str(value or "")
        for delimiter in (",", ";", "\n"):
            text = text.replace(delimiter, "|")
        values = [part.strip() for part in text.split("|")]
    return [item for item in values if item]


def _normalize_oref_payload(payload, provider_name: str = "oref_realtime") -> list[dict]:
    if not payload:
        return []

    if isinstance(payload, list):
        items = []
        for entry in payload:
            items.extend(_normalize_oref_payload(entry, provider_name=provider_name))
        return items

    if not isinstance(payload, dict):
        return []

    records = payload.get("alerts")
    if isinstance(records, list):
        items = []
        for record in records:
            items.extend(_normalize_oref_payload(record, provider_name=provider_name))
        return items

    occurred_at_value = (
        payload.get("alertDate")
        or payload.get("time")
        or payload.get("timestamp")
        or payload.get("date")
    )
    if not occurred_at_value:
        return []

    occurred_at = _parse_source_datetime(occurred_at_value)
    category = THREAT_CATEGORY_MAP.get(
        int(payload.get("cat", payload.get("category", payload.get("threat", 0)))),
        "rocket_missile",
    )
    cities = _split_city_text(payload.get("data") or payload.get("cities") or payload.get("city"))
    if not cities:
        return []

    return [
        {
            "source": provider_name,
            "occurred_at": occurred_at,
            "category": category,
            "city": city,
            "district": "",
            "raw_payload": payload,
        }
        for city in cities
    ]


def _base_oref_headers() -> dict:
    return {
        "User-Agent": settings.REALTIME_USER_AGENT,
        "Referer": settings.REALTIME_REFERER,
        "X-Requested-With": "XMLHttpRequest",
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "he-IL,he;q=0.9,en;q=0.8",
        "Cache-Control": "no-cache",
        "Pragma": "no-cache",
    }


def _fetch_oref_provider() -> ProviderFetchResult:
    urls = getattr(settings, "OREF_REALTIME_URLS", [])
    if not urls:
        return ProviderFetchResult(
            provider="oref_realtime",
            url=None,
            status="disabled",
            events=[],
            error="No OREF_REALTIME_URLS configured",
        )

    headers = _base_oref_headers()
    last_error: str | None = None
    for url in urls:
        try:
            payload = _get_json(url, headers=headers)
            events = _normalize_oref_payload(payload, provider_name="oref_realtime")
            return ProviderFetchResult(
                provider="oref_realtime",
                url=url,
                status="ok" if events else "empty",
                events=events,
                error=None,
                raw_event_count=len(events),
            )
        except Exception as exc:  # noqa: BLE001
            last_error = str(exc)
            continue

    return ProviderFetchResult(
        provider="oref_realtime",
        url=None,
        status="error",
        events=[],
        error=last_error or "Unknown Oref realtime error",
        raw_event_count=0,
    )


def _fetch_backup_notifications_provider() -> ProviderFetchResult:
    url = getattr(settings, "LIVE_BACKUP_NOTIFICATIONS_URL", "")
    if not url:
        return ProviderFetchResult("backup_notifications", None, "disabled", [], "No LIVE_BACKUP_NOTIFICATIONS_URL configured", 0)
    try:
        payload = _get_json(url, headers=_base_oref_headers()) or []
        events = _normalize_oref_payload(payload, provider_name="backup_notifications")
        return ProviderFetchResult("backup_notifications", url, "ok" if events else "empty", events, None, len(events))
    except Exception as exc:  # noqa: BLE001
        return ProviderFetchResult("backup_notifications", url, "error", [], str(exc), 0)


def _fetch_backup_history_provider() -> ProviderFetchResult:
    url = getattr(settings, "LIVE_BACKUP_HISTORY_URL", "")
    if not url:
        return ProviderFetchResult("backup_history_live", None, "disabled", [], "No LIVE_BACKUP_HISTORY_URL configured", 0)
    try:
        payload = _get_json(url, headers=_base_oref_headers()) or []
        events = []
        if isinstance(payload, list):
            for group in payload:
                if isinstance(group, dict) and isinstance(group.get("alerts"), list):
                    events.extend(_normalize_oref_payload(group.get("alerts"), provider_name="backup_history_live"))
                else:
                    events.extend(_normalize_oref_payload(group, provider_name="backup_history_live"))
        else:
            events = _normalize_oref_payload(payload, provider_name="backup_history_live")
        return ProviderFetchResult("backup_history_live", url, "ok" if events else "empty", events, None, len(events))
    except Exception as exc:  # noqa: BLE001
        return ProviderFetchResult("backup_history_live", url, "error", [], str(exc), 0)


def _fetch_extra_provider(url: str, index: int) -> ProviderFetchResult:
    provider_name = f"extra_live_{index + 1}"
    try:
        payload = _get_json(url, headers=_base_oref_headers()) or []
        events = _normalize_oref_payload(payload, provider_name=provider_name)
        return ProviderFetchResult(provider_name, url, "ok" if events else "empty", events, None, len(events))
    except Exception as exc:  # noqa: BLE001
        return ProviderFetchResult(provider_name, url, "error", [], str(exc), 0)


def _provider_priority(provider: str) -> int:
    order = {
        "oref_realtime": 0,
        "backup_notifications": 1,
        "backup_history_live": 2,
    }
    return order.get(provider, 99)


def _event_signature(event: dict) -> tuple:
    return (
        event.get("occurred_at"),
        event.get("category"),
        event.get("city"),
    )


def _merge_provider_events(results: list[ProviderFetchResult]) -> list[dict]:
    by_signature: dict[tuple, dict] = {}
    seen_by_signature: dict[tuple, list[str]] = {}
    for result in sorted(results, key=lambda r: _provider_priority(r.provider)):
        for event in result.events:
            sig = _event_signature(event)
            seen_by_signature.setdefault(sig, []).append(result.provider)
            if sig not in by_signature:
                by_signature[sig] = event.copy()

    merged = []
    for sig, event in by_signature.items():
        providers_seen = seen_by_signature.get(sig, [])
        raw_payload = dict(event.get("raw_payload") or {})
        raw_payload["_comparison"] = {
            "providers_seen": providers_seen,
            "winner": event.get("source"),
        }
        merged.append(
            {
                **event,
                "source": "live_consensus",
                "raw_payload": raw_payload,
            }
        )
    return merged


def _filter_recent_events(events: list[dict], *, max_age_minutes: int) -> list[dict]:
    if max_age_minutes <= 0:
        return events
    now = datetime.now(dt_timezone.utc)
    oldest_allowed = now - timedelta(minutes=max_age_minutes)
    newest_allowed = now + timedelta(minutes=2)
    return [
        event
        for event in events
        if isinstance(event.get("occurred_at"), datetime) and oldest_allowed <= event["occurred_at"] <= newest_allowed
    ]


def fetch_realtime_events() -> list[dict]:
    return fetch_live_events_with_status().events


def fetch_live_events_with_status() -> LiveFetchResult:
    provider_results = [
        _fetch_oref_provider(),
        _fetch_backup_notifications_provider(),
        _fetch_backup_history_provider(),
    ]
    for index, extra_url in enumerate(getattr(settings, "LIVE_EXTRA_URLS", [])):
        provider_results.append(_fetch_extra_provider(extra_url, index))

    max_age_minutes = int(getattr(settings, "LIVE_MAX_EVENT_AGE_MINUTES", 20))
    filtered_results: list[ProviderFetchResult] = []
    for result in provider_results:
        fresh_events = _filter_recent_events(result.events, max_age_minutes=max_age_minutes)
        filtered_status = result.status
        if result.status == "ok" and not fresh_events:
            filtered_status = "empty"
        filtered_results.append(
            ProviderFetchResult(
                provider=result.provider,
                url=result.url,
                status=filtered_status,
                events=fresh_events,
                error=result.error,
                raw_event_count=result.raw_event_count or len(result.events),
            )
        )

    merged_events = _merge_provider_events(filtered_results)
    any_error = any(result.status == "error" for result in filtered_results)
    any_ok = any(result.status == "ok" for result in filtered_results)
    any_enabled = any(result.status in {"ok", "empty"} for result in filtered_results)

    if merged_events:
        status = "ok"
    elif any_ok or any_enabled:
        status = "empty"
    elif any_error:
        status = "error"
    else:
        status = "disabled"

    error_texts = [
        f"{result.provider}: {result.error}"
        for result in filtered_results
        if result.error
    ]
    primary = next((result for result in filtered_results if result.status in {"ok", "empty"}), filtered_results[0])

    details = [
        {
            "provider": result.provider,
            "url": result.url,
            "status": result.status,
            "raw_event_count": result.raw_event_count,
            "event_count": len(result.events),
            "max_age_minutes": max_age_minutes,
            "error": result.error,
        }
        for result in filtered_results
    ]

    return LiveFetchResult(
        events=merged_events,
        source_status=status,
        source_url=primary.url,
        source_event_count=len(merged_events),
        source_error=" | ".join(error_texts) if error_texts else None,
        source_details=details,
    )


def fetch_live_events() -> list[dict]:
    return fetch_live_events_with_status().events


def fetch_history_events(start=None, end=None) -> list[dict]:
    if not settings.HISTORY_SOURCE_URL:
        return []

    metadata = history_city_metadata()
    payload = _get_json(settings.HISTORY_SOURCE_URL) or []
    items = []

    for row in payload:
        if not isinstance(row, list) or len(row) < 4:
            continue
        alert_id, threat, cities, timestamp = row[:4]
        occurred_at = _parse_source_datetime(timestamp)
        if start and occurred_at < start:
            continue
        if end and occurred_at > end:
            continue

        category = THREAT_CATEGORY_MAP.get(int(threat), f"threat_{threat}")
        for city in cities:
            city_info = (metadata.get("cities") or {}).get(city, {})
            area_id = str(city_info.get("area") or "")
            area_info = (metadata.get("areas") or {}).get(area_id, {})
            district = area_info.get("he") or area_info.get("en") or ""
            items.append(
                {
                    "source": "tzevaadom_history",
                    "occurred_at": occurred_at,
                    "category": category,
                    "city": city,
                    "district": district,
                    "raw_payload": {
                        "provider": "tzevaadom",
                        "alert_id": alert_id,
                        "threat": threat,
                        "cities": cities,
                        "timestamp": timestamp,
                    },
                }
            )
    return items
