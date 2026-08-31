from django.urls import path

from . import views

urlpatterns = [
    path("", views.AssetListView.as_view(), name="asset_list"),
    path("refresh-prices/", views.refresh_prices_view, name="refresh_prices"),
    path("<int:pk>/candles/", views.asset_candles_view, name="asset_candles"),
    path("<int:pk>/", views.AssetDetailView.as_view(), name="asset_detail"),
]
