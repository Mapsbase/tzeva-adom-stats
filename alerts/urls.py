from django.urls import path

from .views import CityMetadataView, LatestAlertsView, LiveFeedView, PullHistoryView, PullRealtimeView, RangeOverviewView, TopCitiesView

urlpatterns = [
    path("alerts/latest", LatestAlertsView.as_view(), name="alerts-latest"),
    path("alerts/feed", LiveFeedView.as_view(), name="alerts-feed"),
    path("alerts/pull-realtime", PullRealtimeView.as_view(), name="alerts-pull-realtime"),
    path("alerts/pull-history", PullHistoryView.as_view(), name="alerts-pull-history"),
    path("meta/cities", CityMetadataView.as_view(), name="meta-cities"),
    path("stats/top-cities", TopCitiesView.as_view(), name="top-cities"),
    path("stats/range-overview", RangeOverviewView.as_view(), name="range-overview"),
]
