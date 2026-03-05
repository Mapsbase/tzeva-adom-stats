from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="Alert",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("source", models.CharField(default="redalert", max_length=32)),
                ("occurred_at", models.DateTimeField()),
                ("category", models.CharField(max_length=32)),
                ("city", models.CharField(max_length=128)),
                ("district", models.CharField(blank=True, default="", max_length=128)),
                ("raw_payload", models.JSONField(blank=True, default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={"ordering": ("-occurred_at", "-id")},
        ),
        migrations.AddConstraint(
            model_name="alert",
            constraint=models.UniqueConstraint(
                fields=("source", "occurred_at", "category", "city"),
                name="uq_alert_source_time_category_city",
            ),
        ),
        migrations.AddIndex(
            model_name="alert",
            index=models.Index(fields=["occurred_at"], name="alerts_occurred_idx"),
        ),
        migrations.AddIndex(
            model_name="alert",
            index=models.Index(fields=["city", "occurred_at"], name="alerts_city_time_idx"),
        ),
        migrations.AddIndex(
            model_name="alert",
            index=models.Index(fields=["district", "occurred_at"], name="alerts_district_time_idx"),
        ),
        migrations.AddIndex(
            model_name="alert",
            index=models.Index(fields=["category"], name="alerts_category_idx"),
        ),
    ]
