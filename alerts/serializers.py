from rest_framework import serializers

from .models import Alert
from .fetchers import (
    category_labels,
    city_labels,
    district_labels_from_name,
    history_city_metadata,
    source_labels,
)


class AlertSerializer(serializers.ModelSerializer):
    city_label = serializers.SerializerMethodField()
    city_labels = serializers.SerializerMethodField()
    district_labels = serializers.SerializerMethodField()
    category_labels = serializers.SerializerMethodField()
    source_labels = serializers.SerializerMethodField()
    lat = serializers.SerializerMethodField()
    lng = serializers.SerializerMethodField()

    class Meta:
        model = Alert
        fields = (
            "id",
            "source",
            "occurred_at",
            "category",
            "city",
            "city_label",
            "city_labels",
            "district",
            "district_labels",
            "category_labels",
            "source_labels",
            "lat",
            "lng",
            "raw_payload",
        )

    def get_city_label(self, obj):
        return city_labels(obj.city).get("he") or obj.city

    def get_city_labels(self, obj):
        return city_labels(obj.city)

    def get_district_labels(self, obj):
        return district_labels_from_name(obj.district)

    def get_category_labels(self, obj):
        return category_labels(obj.category)

    def get_source_labels(self, obj):
        return source_labels(obj.source)

    def get_lat(self, obj):
        metadata = history_city_metadata()
        city_info = (metadata.get("cities") or {}).get(obj.city, {})
        return city_info.get("lat")

    def get_lng(self, obj):
        metadata = history_city_metadata()
        city_info = (metadata.get("cities") or {}).get(obj.city, {})
        return city_info.get("lng")
