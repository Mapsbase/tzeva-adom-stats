from django.db import models


class Alert(models.Model):
    source = models.CharField(max_length=32, default="redalert")
    occurred_at = models.DateTimeField()
    category = models.CharField(max_length=32)
    city = models.CharField(max_length=128)
    district = models.CharField(max_length=128, blank=True, default="")
    raw_payload = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-occurred_at", "-id")
        constraints = [
            models.UniqueConstraint(
                fields=["source", "occurred_at", "category", "city"],
                name="uq_alert_source_time_category_city",
            )
        ]
        indexes = [
            models.Index(fields=["occurred_at"], name="alerts_occurred_idx"),
            models.Index(fields=["city", "occurred_at"], name="alerts_city_time_idx"),
            models.Index(fields=["district", "occurred_at"], name="alerts_district_time_idx"),
            models.Index(fields=["category"], name="alerts_category_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.occurred_at.isoformat()} {self.city} {self.category}"
