from django.contrib import admin

from .models import Alert


@admin.register(Alert)
class AlertAdmin(admin.ModelAdmin):
    list_display = ("occurred_at", "city", "district", "category", "source")
    list_filter = ("category", "district", "source")
    search_fields = ("city", "district")
    ordering = ("-occurred_at", "-id")
