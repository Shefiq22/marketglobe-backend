from django.urls import path

from . import views

urlpatterns = [
    path("events/", views.EconomicEventListView.as_view(), name="economic_events"),
    path("market/", views.MarketNewsListView.as_view(), name="market_news"),
    path("asset/<int:asset_id>/", views.AssetNewsListView.as_view(), name="asset_news"),
    path("refresh/", views.refresh_news, name="refresh_news"),
]
